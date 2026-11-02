import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { URL } from 'node:url';
import { join } from 'node:path';
import { requestFromEvent, verifyCurrentComment, verifyCurrentIssue, taskCap, reserveReceipt, invokePrivateRunner, validateLiveRequest } from './deepseek-dispatch.mjs';

function goodEvent() {
  return {
    repository: { full_name: 'mbelinkie/vera-script-to-timeline', owner: { login: 'mbelinkie' } },
    issue: { number: 396 },
    comment: { id: 321, body: '/deepseek dispatch', user: { login: 'mbelinkie' } }
  };
}
function goodIssue() {
  return {
    number: 396, state: 'open', body: '## DeepSeek Handoff\nApproved public task only.',
    labels: ['type:implementation', 'chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'].map(name => ({ name }))
  };
}

test('accept exactly an owner-authored issue dispatch', () => {
  assert.deepEqual(requestFromEvent(goodEvent()), { issue: 396, commentId: 321 });
  const bot = goodEvent(); bot.comment.user.login = 'chat-review-bot';
  assert.throws(() => requestFromEvent(bot));
  assert.deepEqual(requestFromEvent(bot, ['chat-review-bot']), { issue: 396, commentId: 321 });
  assert.equal(verifyCurrentIssue(goodIssue(), 396), true);
});

test('matches the live dispatch comment to its event identity', () => {
  const request = { issue: 396, commentId: 321 };
  const live = {
    id: 321, body: '/deepseek dispatch', issue_url: 'https://api.github.com/repos/mbelinkie/vera-script-to-timeline/issues/396',
    user: { login: 'mbelinkie' }
  };
  assert.equal(verifyCurrentComment(live, request, 'mbelinkie'), true);
  for (const change of [
    x => { x.id = 322; },
    x => { x.body = '/deepseek dispatch extra'; },
    x => { x.issue_url = 'https://api.github.com/repos/mbelinkie/vera-script-to-timeline/issues/397'; },
    x => { x.user.login = 'other'; }
  ]) {
    const comment = JSON.parse(JSON.stringify(live));
    change(comment);
    assert.throws(() => verifyCurrentComment(comment, request, 'mbelinkie'));
  }
});

test('reject wrong repo, non-owner, non-exact command, PR and malformed IDs', () => {
  for (const change of [
    x => { x.repository.full_name = 'attacker/other'; },
    x => { x.comment.user.login = 'outsider'; },
    x => { x.comment.body = '/deepseek dispatch; rm -rf'; },
    x => { x.comment.body = '/deepseek dispatch\nmore'; },
    x => { x.issue.pull_request = {}; },
    x => { x.issue.number = -1; },
    x => { x.comment.id = '321'; }
  ]) {
    const e = goodEvent(); change(e);
    assert.throws(() => requestFromEvent(e));
  }
});

test('reject unreviewed, pending, closed, or mismatched issue', () => {
  for (const change of [
    x => { x.labels = [{ name: 'deepseek-ready' }]; },
    x => { x.labels = [{ name: 'chat-reviewed' }]; },
    x => { x.labels = x.labels.filter(l => l.name !== 'deepseek-eligible'); },
    x => { x.labels = x.labels.filter(l => l.name !== 'deepseek-dispatch'); },
    x => { x.labels.push({ name: 'chat-review-pending' }); },
    ...['type:design', 'type:ux', 'type:research', 'type:product', 'execution:codex', 'execution:design', 'execution:human', 'deepseek-excluded'].map(name => x => { x.labels.push({ name }); }),
    x => { x.labels.push({ name: 'needs:model-escalation' }); },
    x => { x.labels.push({ name: 'owner:codex' }); },
    x => { x.labels.push({ name: 'owner:claude' }); },
    x => { x.labels = x.labels.filter(l => l.name !== 'type:implementation'); },
    x => { x.labels.push({ name: 'type:bug' }); },
    x => { x.labels = x.labels.map(l => l.name === 'type:implementation' ? { name: 'type:investigation' } : l); },
    x => { x.body = ''; },
    x => { x.body = '## DeepSeek Handoff'; },
    x => { x.body = '## DeepSeek Handoff\n   \n## Other section\nUnrelated details'; },
    x => { x.body = '## DeepSeek Handoff\n<!-- notes only -->'; },
    x => { x.state = 'closed'; },
    x => { x.number = 999; },
    x => { x.pull_request = {}; }
  ]) {
    const issue = goodIssue(); change(issue);
    assert.throws(() => verifyCurrentIssue(issue, 396));
  }
});

test('require a finite positive bounded task cap', () => {
  assert.equal(taskCap('0.25'), 0.25);
  for (const value of [undefined, '', '0', '0.2501', '10', 'NaN', 'Infinity', '0.00001', '5 USD', '-1']) {
    assert.throws(() => taskCap(value));
  }
});

test('GitHub validation rechecks exact comment identity and the canonical current review', async () => {
  const issue = {
    number: 396, title: 'Synthetic implementation issue', body: '## DeepSeek Handoff\nBounded public source change.',
    state: 'open', labels: ['type:implementation', 'chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'],
    comments: 1,
    repository_url: 'https://api.github.com/repos/mbelinkie/vera-script-to-timeline',
    html_url: 'https://github.com/mbelinkie/vera-script-to-timeline/issues/396'
  };
  const approval = {
    id: 654, user: { login: 'mbelinkie' }, created_at: '2026-11-02T12:00:00Z', updated_at: '2026-11-02T12:00:00Z',
    performed_via_github_app: null,
    body: '<!-- VERA_CHAT_REVIEW_V1 ' + JSON.stringify({
      revision: createHash('sha256').update(JSON.stringify([issue.title, issue.body])).digest('hex'),
      producer: 'mbelinkie', reviewedAt: '2026-11-02T12:00:00.000Z', promptVersion: '1'
    }) + ' -->'
  };
  const dispatchComment = {
    id: 321, body: '/deepseek dispatch', issue_url: issue.html_url.replace('github.com', 'api.github.com/repos').replace('/issues/396', '/issues/396'),
    user: { login: 'mbelinkie' }
  };
  const event = goodEvent();
  const fetchCalls = [];
  const fetchJson = async url => {
    fetchCalls.push(url);
    if (url.endsWith('/issues/comments/321')) return dispatchComment;
    if (url.endsWith('/issues/396')) return issue;
    throw new Error('Unexpected request');
  };
  const readGh = args => {
    if (args[1] === 'repos/mbelinkie/vera-script-to-timeline/issues/396') return JSON.stringify(issue);
    if (args[3] === 'repos/mbelinkie/vera-script-to-timeline/issues/396/comments?per_page=100') {
      return JSON.stringify([[approval]]);
    }
    throw new Error('Unexpected canonical-gate read');
  };
  const result = await validateLiveRequest(event, { token: 'read-only-test-token', taskCapUsd: '0.25', fetchJson, readGh });
  assert.deepEqual(result, { request: { issue: 396, commentId: 321 }, reviewCommentId: 654 });
  assert.equal(fetchCalls.length, 3);
});

test('receipt is allocated before calls and refuses duplicate issue attempts', () => {
  const root = mkdtempSync(join(tmpdir(), 'vera-deepseek-receipt-'));
  try {
    const receipt = reserveReceipt(join(root, 'receipts'), 396, 321);
    assert.equal(JSON.parse(readFileSync(receipt, 'utf8')).state, 'reserved');
    assert.throws(() => reserveReceipt(join(root, 'receipts'), 396, 322));
    assert.notEqual(reserveReceipt(join(root, 'receipts'), 397, 323), receipt);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('private runner does not leak worker stdout/stderr to public job logs', () => {
  // Exercise the real child-process stdio behavior inside a captured subprocess.
  // A regression to stdio:inherit would print both canaries and fail the test.
  const workerScript = [
    "process.stdout.write('PRIVATE_STDOUT_CANARY\\n');",
    "process.stderr.write('PRIVATE_STDERR_CANARY\\n');",
    "process.exit(7);"
  ].join('');
  const harness = [
    `import { invokePrivateRunner } from ${JSON.stringify(new URL('./deepseek-dispatch.mjs', import.meta.url).href)};`,
    `const result = invokePrivateRunner(process.execPath, ['-e', ${JSON.stringify(workerScript)}], {PATH: process.env.PATH || ''});`,
    "if (result.status !== 7 || result.stdout !== null || result.stderr !== null) process.exit(91);",
    "process.stdout.write('SAFE_STATUS_ONLY');"
  ].join('\n');
  const probe = spawnSync(process.execPath, ['--input-type=module', '-e', harness], { encoding: 'utf8' });
  assert.equal(probe.status, 0);
  assert.equal(probe.stdout, 'SAFE_STATUS_ONLY');
  assert.equal(probe.stderr, '');
});

test('private runner preserves bounded no-shell invocation parameters', () => {
  let called = false;
  const result = invokePrivateRunner('/safe/private-runner', ['396', '321'], { HOME: '/private' },
    (runner, args, options) => {
      called = true;
      assert.equal(runner, '/safe/private-runner');
      assert.deepEqual(args, ['396', '321']);
      assert.deepEqual(options.env, { HOME: '/private' });
      assert.equal(options.shell, false);
      assert.equal(options.stdio, 'ignore');
      assert.equal(options.timeout, 40 * 60 * 1000);
      return { status: 1 };
    });
  assert.equal(called, true);
  assert.equal(result.status, 1);
});
