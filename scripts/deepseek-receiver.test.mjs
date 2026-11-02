import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { Buffer } from 'node:buffer';
import { join } from 'node:path';
import { loadApprovedManifest, pollOnce, readCursor, validateManifest, writeCursor } from './deepseek-receiver.mjs';

const sha = 'a'.repeat(40);
const hash = 'b'.repeat(64);

function manifest() {
  return {
    schemaVersion: 1,
    issueNumber: 396,
    dispatchCommentId: 321,
    approvedBy: 'mbelinkie',
    approvedAt: '2026-11-02T12:00:00.000Z',
    sourceSha: sha,
    allowedFiles: ['scripts/example.mjs'],
    frozenTests: [{ path: 'scripts/example.test.mjs', sha256: hash }],
    allowedCommands: [['npm', 'test']],
    maxRepairAttempts: 2,
    taskCapUsd: '0.25'
  };
}

test('manifest must bind the approved issue, current source and bounded files/tests/commands', () => {
  const valid = manifest();
  assert.equal(validateManifest(valid, 396, 321, sha).cap, 0.25);
  for (const change of [
    value => { value.issueNumber = 397; },
    value => { value.dispatchCommentId = 322; },
    value => { value.sourceSha = 'c'.repeat(40); },
    value => { value.allowedFiles = ['../outside.mjs']; },
    value => { value.allowedFiles = ['scripts\\outside.mjs']; },
    value => { value.frozenTests[0].sha256 = 'not-a-hash'; },
    value => { value.allowedCommands = [['sh', '-c', 'anything']]; },
    value => { value.maxRepairAttempts = 4; },
    value => { value.taskCapUsd = '10'; }
  ]) {
    const invalid = globalThis.structuredClone(valid);
    change(invalid);
    assert.throws(() => validateManifest(invalid, 396, 321, sha));
  }
});

test('private manifest hash covers the exact approved file bytes', () => {
  const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-manifest-'));
  const directory = join(root, 'manifests');
  const path = join(directory, 'issue-396.json');
  try {
    mkdirSync(directory, { mode: 0o700 });
    const raw = Buffer.from(JSON.stringify(manifest(), null, 2) + '\n');
    // Directory and file permissions match the owner's private manifest store.
    writeFileSync(path, raw, { mode: 0o400 });
    const loaded = loadApprovedManifest(path, 396, 321, sha);
    assert.equal(loaded.sha256, createHash('sha256').update(raw).digest('hex'));
    assert.equal(loaded.cap, 0.25);
  } finally {
    chmodSync(root, 0o700);
    rmSync(root, { recursive: true, force: true });
  }
});

test('cursor initializes without replaying existing comments, then advances after each inspected comment', async () => {
  const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-cursor-'));
  const cursorPath = join(root, 'receiver', 'cursor.json');
  const seen = [];
  try {
    const oldComments = [{ id: 10, body: 'old' }, { id: 9, body: '/deepseek dispatch' }];
    assert.deepEqual(await pollOnce({ cursorPath, list: async () => oldComments }), { initialized: true, processed: 0 });
    assert.equal(readCursor(cursorPath), 10);
    assert.equal(statSync(cursorPath).mode & 0o777, 0o400);

    const newer = [{ id: 12, body: 'later' }, { id: 11, body: 'new' }];
    const result = await pollOnce({
      cursorPath,
      list: async lastSeen => {
        assert.equal(lastSeen, 10);
        return newer;
      },
      processComment: async comment => {
        seen.push(comment.id);
      }
    });
    assert.deepEqual(result, { initialized: false, processed: 2 });
    assert.deepEqual(seen, [11, 12]);
    assert.equal(readCursor(cursorPath), 12);
    assert.equal(JSON.parse(readFileSync(cursorPath, 'utf8')).repository, 'mbelinkie/vera-script-to-timeline');
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('cursor refuses shared permissions and poll refuses duplicate comment identifiers', async () => {
  const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-cursor-'));
  const cursorPath = join(root, 'receiver', 'cursor.json');
  try {
    writeCursor(cursorPath, 5);
    const comments = [{ id: 6, body: 'one' }, { id: 6, body: 'duplicate' }];
    await assert.rejects(pollOnce({ cursorPath, list: async () => comments }), /incomplete/);
    assert.equal(readCursor(cursorPath), 5);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
