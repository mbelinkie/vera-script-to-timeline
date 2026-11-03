import test from 'node:test';
import assert from 'node:assert/strict';
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { Buffer } from 'node:buffer';
import { join } from 'node:path';
import { listRecentComments, loadApprovedManifest, pollOnce, processDispatchComment, readCursor, validateManifest, writeCursor } from './deepseek-receiver.mjs';
import { COMMAND, REPO } from './deepseek-dispatch.mjs';

const sha = 'a'.repeat(40);
const hash = 'b'.repeat(64);

function manifest() {
  return {
    schema: 1, repository: REPO, issue: 396, dispatch_comment_id: 321,
    transport_contract: 'VERA_DEEPSEEK_RECEIVER_V1', adapter_sha256: hash,
    public_synthetic_only: true, operator_approved: true,
    base_sha: sha, editable_file: 'scripts/example.py', editable_sha256: hash,
    frozen_files: { 'scripts/example.test.py': hash },
    checks: [['/usr/bin/python3', '-m', 'unittest']],
    source_repo: '/synthetic/public-source', edit_scope: { mode: 'full_file', approve_entire_file: true },
    max_rounds: 2, max_output_tokens: 512, task_cap_usd: '0.25',
    task_instructions: 'Apply only the preapproved replacement to the public synthetic fixture.',
    live_enabled: false, mock_replacement: 'print("synthetic")\n'
  };
}

test('manifest must bind the approved issue, current source and bounded files/tests/commands', () => {
  const valid = manifest();
  assert.equal(validateManifest(valid, 396, 321, sha).cap, 0.25);
  for (const change of [
    value => { value.issue = 397; },
    value => { value.dispatch_comment_id = 322; },
    value => { value.base_sha = 'c'.repeat(40); },
    value => { value.editable_file = '../outside.py'; },
    value => { value.editable_file = 'scripts\\outside.py'; },
    value => { value.frozen_files['scripts/example.test.py'] = 'not-a-hash'; },
    value => { value.checks = [['/bin/sh', '-c', 'anything']]; },
    value => { value.max_rounds = 4; },
    value => { value.task_cap_usd = '10'; },
    value => { value.live_enabled = true; },
    value => { delete value.transport_contract; },
    value => { delete value.adapter_sha256; }
  ]) {
    const invalid = globalThis.structuredClone(valid);
    change(invalid);
    assert.throws(() => validateManifest(invalid, 396, 321, sha));
  }
});

test('receiver binds the adapter contract and refuses source, review, or runner mismatches', async () => {
  for (const scenario of ['success', 'changed-main', 'stale-review', 'changed-adapter', 'network-error', 'transient-final']) {
    const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-contract-'));
    const manifestDir = join(root, 'tasks');
    const receiptRoot = join(root, 'receipts');
    const runner = join(root, 'synthetic-runner');
    try {
      mkdirSync(manifestDir, { mode: 0o700 });
      const runnerBytes = '#!/bin/sh\nexit 99\n';
      writeFileSync(runner, runnerBytes, { mode: 0o700 });
      const task = { ...manifest(), adapter_sha256: createHash('sha256').update(runnerBytes).digest('hex') };
      if (scenario === 'changed-adapter') task.adapter_sha256 = hash;
      const raw = JSON.stringify(task, null, 2) + '\n';
      writeFileSync(join(manifestDir, 'issue-396.json'), raw, { mode: 0o400 });
      const issue = {
        number: 396, title: 'Synthetic transport proof', body: '## DeepSeek Handoff\nOnly the approved synthetic fixture.',
        state: 'open', comments: 2, updated_at: '2026-11-02T12:01:00Z',
        labels: ['type:implementation', 'chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'],
        repository_url: 'https://api.github.com/repos/' + REPO,
        html_url: 'https://github.com/' + REPO + '/issues/396'
      };
      const comment = {
        id: 321, body: COMMAND, user: { login: 'mbelinkie' },
        issue_url: 'https://api.github.com/repos/' + REPO + '/issues/396',
        created_at: '2026-11-02T12:01:00Z', updated_at: '2026-11-02T12:01:00Z', performed_via_github_app: null
      };
      const approval = {
        id: 123, user: { login: 'mbelinkie' }, created_at: '2026-11-02T12:00:00Z', updated_at: '2026-11-02T12:00:00Z',
        performed_via_github_app: null,
        body: '<!-- VERA_CHAT_REVIEW_V1 ' + JSON.stringify({
          revision: createHash('sha256').update(JSON.stringify([issue.title, issue.body])).digest('hex'),
          producer: 'mbelinkie', reviewedAt: '2026-11-02T12:00:00.000Z', promptVersion: '1'
        }) + ' -->'
      };
      if (scenario === 'stale-review') approval.body = approval.body.replace('"revision":"', '"revision":"invalid-');
      let mainReads = 0;
      let issueReads = 0;
      let calls = 0;
      const options = {
        manifestDir, receiptRoot, runner, preflight: () => ({ ready: true }),
        fetchImpl: async url => {
          const path = new globalThis.URL(url).pathname;
          let value;
          if (path.endsWith('/issues/396')) {
            issueReads += 1;
            if (scenario === 'network-error' && issueReads === 1) throw new TypeError('temporary network failure');
            if (scenario === 'transient-final' && issueReads === 3) return { ok: false, status: 403 };
            value = issue;
          }
          else if (path.endsWith('/issues/comments/321')) value = comment;
          else if (path.endsWith('/commits/main')) value = { sha: scenario === 'changed-main' && ++mainReads > 1 ? 'c'.repeat(40) : sha };
          else throw new Error('Unexpected GitHub read');
          return { ok: true, json: async () => globalThis.structuredClone(value) };
        },
        readGh: args => args.at(-1).endsWith('/comments?per_page=100')
          ? JSON.stringify([[approval, comment]]) : JSON.stringify(issue),
        invoke: (path, args, env) => {
          calls += 1;
          assert.equal(path, runner);
          assert.deepEqual(args, ['396', '321']);
          assert.equal(env.VERA_DEEPSEEK_EXECUTION_MODE, 'mock');
          assert.equal(env.VERA_DEEPSEEK_SOURCE_SHA, sha);
          assert.equal(env.VERA_DEEPSEEK_MANIFEST_SHA256, createHash('sha256').update(raw).digest('hex'));
          assert.equal(JSON.parse(readFileSync(env.VERA_DEEPSEEK_RECEIPT, 'utf8')).state, 'reserved');
          assert.equal(env.GITHUB_TOKEN, undefined);
          return { status: 0 };
        }
      };
      const success = scenario === 'success';
      if (scenario === 'network-error' || scenario === 'transient-final') {
        await assert.rejects(processDispatchComment(comment, options), scenario === 'network-error'
          ? /temporary network failure/ : /HTTP 403/);
        assert.equal(calls, 0);
        assert.throws(() => statSync(join(receiptRoot, 'issue-396')), { code: 'ENOENT' });
        continue;
      }
      assert.deepEqual(await processDispatchComment(comment, options), { state: success ? 'worker-returned' : 'refused' });
      assert.equal(calls, success ? 1 : 0);
      assert.deepEqual(await processDispatchComment(comment, options), { state: success ? 'duplicate' : 'refused' });
      assert.equal(calls, success ? 1 : 0);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
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
    chmodSync(cursorPath, 0o600);
    assert.throws(() => readCursor(cursorPath), /unsafe type, owner, or permissions/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('comment polling initializes newest first, then resumes oldest first from its timestamp', async () => {
  const urls = [];
  const fetchImpl = async url => {
    const parsed = new globalThis.URL(url);
    urls.push(parsed);
    const comments = parsed.searchParams.get('direction') === 'desc'
      ? [{ id: 52, body: 'newest' }, { id: 51, body: 'older' }]
      : [{ id: 43, body: 'next', created_at: '2026-11-02T20:00:01Z' }];
    return { ok: true, json: async () => comments, headers: { get: () => null } };
  };

  assert.deepEqual(await listRecentComments(fetchImpl), [
    { id: 52, body: 'newest' }, { id: 51, body: 'older' }
  ]);
  assert.equal(urls[0].searchParams.get('direction'), 'desc');
  assert.equal(urls[0].searchParams.has('since'), false);

  assert.deepEqual(await listRecentComments(fetchImpl, 42, '2026-11-02T20:00:00Z'), [
    { id: 43, body: 'next', created_at: '2026-11-02T20:00:01Z' }
  ]);
  assert.equal(urls[1].searchParams.get('direction'), 'asc');
  assert.equal(urls[1].searchParams.get('since'), '2026-11-02T19:59:59.000Z');
});

test('gone issue comments advance the cursor while rate limits remain retryable', async () => {
  const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-gone-comment-'));
  const cursorPath = join(root, 'receiver', 'cursor.json');
  const comment = {
    id: 6, body: COMMAND, user: { login: 'mbelinkie' },
    issue_url: 'https://api.github.com/repos/' + REPO + '/issues/396',
    created_at: '2026-11-02T19:00:00Z', updated_at: '2026-11-02T19:00:00Z'
  };
  try {
    writeCursor(cursorPath, 5, '2026-11-02T18:00:00Z');
    const gone = await pollOnce({
      cursorPath,
      list: async () => [comment],
      fetchImpl: async () => ({ ok: false, status: 404 })
    });
    assert.deepEqual(gone, { initialized: false, processed: 1 });
    assert.equal(readCursor(cursorPath), 6);

    writeCursor(cursorPath, 5, '2026-11-02T18:00:00Z');
    await assert.rejects(pollOnce({
      cursorPath,
      list: async () => [comment],
      fetchImpl: async () => ({ ok: false, status: 403 })
    }), /HTTP 403/);
    assert.equal(readCursor(cursorPath), 5);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('large comment backlogs advance in bounded oldest-first polls', async () => {
  const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-backlog-'));
  const cursorPath = join(root, 'receiver', 'cursor.json');
  const start = Date.UTC(2026, 10, 2, 19, 0, 0);
  const allComments = Array.from({ length: 1100 }, (_, index) => {
    const id = 101 + index;
    return { id, body: 'comment ' + id, created_at: new Date(start + id * 1000).toISOString() };
  });
  const fetchImpl = async url => {
    const parsed = new globalThis.URL(url);
    assert.equal(parsed.searchParams.get('direction'), 'asc');
    assert.equal(parsed.searchParams.get('page'), '1');
    const since = Date.parse(parsed.searchParams.get('since'));
    const comments = allComments.filter(comment => Date.parse(comment.created_at) >= since).slice(0, 100);
    return {
      ok: true,
      json: async () => comments,
      headers: { get: () => null }
    };
  };
  try {
    writeCursor(cursorPath, 100, '2026-11-02T18:00:00Z');
    const processed = [];
    for (let batch = 0; batch < 20 && processed.length < allComments.length; batch += 1) {
      const result = await pollOnce({
        cursorPath, fetchImpl,
        processComment: async comment => processed.push(comment.id)
      });
      assert.equal(result.initialized, false);
      assert.ok(result.processed > 0 && result.processed <= 100);
    }
    assert.equal(processed.length, 1100);
    assert.equal(processed[0], 101);
    assert.equal(processed.at(-1), 1200);
    assert.equal(readCursor(cursorPath), 1200);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
