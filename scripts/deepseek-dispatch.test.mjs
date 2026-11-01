import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { requestFromEvent, verifyCurrentIssue, taskCap, reserveReceipt } from './deepseek-dispatch.mjs';

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
    labels: [{ name: 'chat-reviewed' }, { name: 'deepseek-ready' }]
  };
}

test('accept exactly an owner-authored issue dispatch', () => {
  assert.deepEqual(requestFromEvent(goodEvent()), { issue: 396, commentId: 321 });
  const bot = goodEvent(); bot.comment.user.login = 'chat-review-bot';
  assert.throws(() => requestFromEvent(bot));
  assert.deepEqual(requestFromEvent(bot, ['chat-review-bot']), { issue: 396, commentId: 321 });
  assert.equal(verifyCurrentIssue(goodIssue(), 396), true);
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
    x => { x.labels.push({ name: 'chat-review-pending' }); },
    x => { x.labels.push({ name: 'needs:model-escalation' }); },
    x => { x.body = ''; },
    x => { x.state = 'closed'; },
    x => { x.number = 999; },
    x => { x.pull_request = {}; }
  ]) {
    const issue = goodIssue(); change(issue);
    assert.throws(() => verifyCurrentIssue(issue, 396));
  }
});

test('require a finite positive bounded task cap', () => {
  assert.equal(taskCap('0.5'), 0.5);
  assert.equal(taskCap('10'), 10);
  for (const value of [undefined, '', '0', '10.0001', '11', 'NaN', 'Infinity', '0.00001', '5 USD', '-1']) {
    assert.throws(() => taskCap(value));
  }
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
