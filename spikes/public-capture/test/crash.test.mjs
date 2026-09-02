import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { fileURLToPath } from 'node:url';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { capture } from '../capture.mjs';
import { LocalStore } from '../store.mjs';
import { PROFILE, hash } from '../profile.mjs';
import { temporaryStore, stubRender } from './helpers.mjs';

test('SIGKILL at acquisition/publication boundaries leaves atomic history and auditable recovery', async () => {
  for (const point of ['after-job-directory', 'after-admission', 'before-browser', 'after-browser', 'after-artifact-stage', 'after-provenance-stage', 'before-publish', 'after-publish']) {
    const root = await temporaryStore();
    await capture({ root, command: 'baseline', render: stubRender(11) });
    const store = new LocalStore(root);
    const baseline = (await store.history())[0];
    const baselineReceipt = hash(await readFile(path.join(root, 'commits', baseline.directory, 'provenance.json')));
    const child = spawn(process.execPath, [fileURLToPath(new URL('./crash-worker.mjs', import.meta.url)), root, point], { stdio: 'ignore' });
    const [code, signal] = await once(child, 'exit');
    assert.equal(code, null, point); assert.equal(signal, 'SIGKILL', point);
    // OS releases the helper's lock when its stdin reaches EOF. This handshake
    // is asynchronous to child exit; wait only for a real lock-busy result.
    let result;
    for (let retry = 0; retry < 20; retry += 1) {
      try {
        result = await capture({ root, command: 'crash-command', render: async () => assert.fail('no implicit retry') });
        break;
      } catch (error) {
        if (!error.message.includes('store_busy')) throw error;
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
    }
    assert.equal(result?.result, point === 'after-publish' ? 'committed' : 'failed', point);
    const history = await store.history();
    assert.equal(history.length, point === 'after-publish' ? 2 : 1, point);
    assert.equal(hash(history[0].raster), hash(baseline.raster));
    assert.equal(hash(await readFile(path.join(root, 'commits', baseline.directory, 'provenance.json'))), baselineReceipt);
    const next = await capture({ root, command: 'explicit-new-command', render: stubRender(99) });
    assert.equal(next.result, 'committed', point);
    if (point !== 'after-publish') assert.equal(result.code, 'abandoned_after_process_loss');
  }
});

test('lease expires at commit even after valid rendering and staging', async (t) => {
  const root = await temporaryStore();
  t.mock.timers.enable({ apis: ['Date'], now: Date.now() });
  const result = await capture({ root, command: 'lease', render: stubRender(), hit: async (where) => {
    if (where === 'before-publish') t.mock.timers.tick(PROFILE.limits.leaseMs + 1);
  } });
  assert.equal(result.code, 'lease_expired');
  assert.equal((await new LocalStore(root).history()).length, 0);
});

test('staging corruption is rechecked immediately before atomic publication', async () => {
  const root = await temporaryStore();
  const result = await capture({ root, command: 'corrupt-stage', render: stubRender(), hit: async (where) => {
    if (where !== 'before-publish') return;
    const stage = (await readdir(path.join(root, 'staging'))).find((name) => /^000001-/.test(name));
    await writeFile(path.join(root, 'staging', stage, 'artifact.png'), 'injected corrupted bytes');
  } });
  assert.equal(result.code, 'staged_integrity_failure');
  assert.equal((await new LocalStore(root).history()).length, 0);
});
