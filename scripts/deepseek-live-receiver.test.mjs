import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { liveIdentity, pollOnce, processDispatchComment, validateManifest } from './deepseek-receiver.mjs';
import { liveApprovalMetadata } from './deepseek-live-gate.mjs';
import { issueRevision } from './chat-review-current.mjs';
import { COMMAND, REPO } from './deepseek-dispatch.mjs';

const sha = 'a'.repeat(40);
const hash = 'b'.repeat(64);
const digest = bytes => createHash('sha256').update(bytes).digest('hex');

function liveManifest() {
  const value = {
    schema: 2, transport_contract: 'VERA_DEEPSEEK_RECEIVER_V2', execution_mode: 'live',
    live_contract: 'VERA_DEEPSEEK_LIVE_V2', repository: REPO, issue: 421, dispatch_comment_id: 321,
    adapter_sha256: hash, public_synthetic_only: true, operator_approved: true,
    base_sha: sha, editable_file: 'scripts/example.py', editable_sha256: hash,
    frozen_files: { 'scripts/example.test.py': hash }, checks: [['/usr/bin/python3', 'scripts/example.test.py']],
    source_repo: '/synthetic/public-source', edit_scope: { mode: 'full_file', approve_entire_file: true },
    max_rounds: 1, max_output_tokens: 4096, max_input_units: 20000,
    task_cap_usd: '0.25', campaign_cap_usd: '0.25', lifetime_cap_usd: '10', reasoning_effort: 'high',
    task_instructions: 'Repair only the public synthetic target so its frozen independent test passes.',
    live_enabled: true, model: 'deepseek-flash', attempt_id: 'attempt-synthetic-one', campaign: 'campaign-synthetic-one',
    reconciliation_sha256: hash, ledger_sha256: hash, pricing_verified_on: new Date().toISOString().slice(0, 10)
  };
  value.verified_rates = liveApprovalMetadata(liveIdentity(value, hash)).verifiedRates;
  return value;
}

test('V2 live mode requires exact independent single-attempt limits and never inherits mock/continuation authority', () => {
  assert.equal(validateManifest(liveManifest(), 421, 321, sha).mode, 'live');
  const changes = [
    { schema: 1 }, { execution_mode: undefined }, { execution_mode: 'unknown' },
    { execution_mode: 'mock' }, { live_enabled: false }, { max_rounds: 2 },
    { task_cap_usd: '0.26' }, { campaign_cap_usd: '1' }, { lifetime_cap_usd: '11' },
    { max_input_units: 20001 }, { max_output_tokens: 24001 }, { model: 'unapproved-model' },
    { mock_replacement: 'preapproved mock content' }, { continuation_contract: 'VERA_DEEPSEEK_CONTINUATION_V1' },
    { ledger_sha256: 'invalid' }, { reconciliation_sha256: 'invalid' },
    { pricing_verified_on: '2000-01-01' }, { verified_rates: {} }, { reasoning_effort: 'low' }
  ];
  for (const change of changes) assert.throws(() => validateManifest({ ...liveManifest(), ...change }, 421, 321, sha));
  const mock = { ...liveManifest(), execution_mode: 'mock', live_enabled: false, mock_replacement: 'synthetic' };
  assert.equal(validateManifest(mock, 421, 321, sha).mode, 'mock');
});

test('receiver invokes only separately approved live mode after read-only host checks and preserves controller receipt', async () => {
  for (const scenario of ['success', 'disabled', 'wrong-task', 'revoked', 'host-refused', 'manifest-drift', 'build-drift', 'uncertain', 'wrong-target', 'missing-target', 'live-read-timeout', 'main-read-timeout']) {
    const root = mkdtempSync(join(tmpdir(), 'vera-live-receiver-'));
    try {
      const manifestDir = join(root, 'tasks');
      const receiptRoot = join(root, 'receipts');
      const runner = join(root, 'runner');
      mkdirSync(manifestDir, { mode: 0o700 });
      mkdirSync(receiptRoot, { mode: 0o700 });
      const runnerBytes = '#!/bin/sh\nexit 99\n';
      writeFileSync(runner, runnerBytes, { mode: 0o700 });
      const task = { ...liveManifest(), adapter_sha256: digest(runnerBytes) };
      const manifestPath = join(manifestDir, 'issue-421.json');
      const raw = JSON.stringify(task) + '\n';
      writeFileSync(manifestPath, raw, { mode: 0o400 });
      const metadata = liveApprovalMetadata(liveIdentity(task, digest(raw)));
      if (scenario === 'wrong-task') metadata.manifestSha256 = hash;
      const issue = {
        number: 421, title: 'Synthetic live receiver task', state: 'open', comments: 2,
        body: '## DeepSeek Handoff\nOne exact task.\n<!-- VERA_DEEPSEEK_LIVE_V2 ' + JSON.stringify(metadata) + ' -->',
        labels: ['type:implementation', 'chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'],
        updated_at: '2026-11-03T14:00:00Z', repository_url: `https://api.github.com/repos/${REPO}`,
        html_url: `https://github.com/${REPO}/issues/421`
      };
      const comment = { id: 321, body: COMMAND, user: { login: 'mbelinkie' },
        issue_url: `https://api.github.com/repos/${REPO}/issues/421`, performed_via_github_app: null,
        created_at: '2026-11-03T14:00:00Z', updated_at: '2026-11-03T14:00:00Z' };
      const review = { id: 322, user: { login: 'mbelinkie' }, performed_via_github_app: null,
        created_at: '2026-11-03T14:01:00Z', updated_at: '2026-11-03T14:01:00Z',
        body: '<!-- VERA_CHAT_REVIEW_V1 ' + JSON.stringify({ revision: issueRevision(issue.title, issue.body),
          producer: 'mbelinkie', reviewedAt: '2026-11-03T14:01:00.000Z', promptVersion: '1' }) + ' -->' };
      let calls = 0;
      let preflights = 0;
      const read = args => args.at(-1).includes('/comments?') ? JSON.stringify([[comment, review]]) : JSON.stringify(issue);
      const options = {
        manifestDir, receiptRoot, runner, liveEnabled: scenario !== 'disabled', readGh: read,
        liveTarget: scenario === 'missing-target' ? null : { issue: scenario === 'wrong-target' ? 422 : 421, commentId: 321 },
        readLive: args => {
          if (scenario === 'revoked') throw new Error('Current review revoked');
          if (scenario === 'live-read-timeout') throw new Error('Public GitHub review read failed');
          if (scenario === 'main-read-timeout') throw new Error('Public main ref read failed');
          if (args.at(-1).endsWith('/git/ref/heads/main')) {
            return JSON.stringify({ ref: 'refs/heads/main', object: { type: 'commit', sha } });
          }
          return read(args);
        },
        fetchImpl: async url => ({ ok: true, json: async () => globalThis.structuredClone(
          url.endsWith('/commits/main') ? { sha } : url.endsWith('/issues/comments/321') ? comment : issue) }),
        preflight: () => {
          preflights += 1;
          assert.equal(existsSync(join(receiptRoot, 'issue-421')), false);
          if (scenario === 'host-refused') throw new Error('Repair owner-only state permissions');
          if (scenario === 'manifest-drift') {
            chmodSync(manifestPath, 0o600);
            writeFileSync(manifestPath, raw + ' ');
            chmodSync(manifestPath, 0o400);
          }
          if (scenario === 'build-drift') writeFileSync(runner, runnerBytes + '# changed');
        },
        invoke: (path, args, env) => {
          calls += 1;
          assert.equal(path, runner);
          assert.deepEqual(args, ['421', '321']);
          assert.equal(preflights, 1);
          assert.equal(env.VERA_DEEPSEEK_EXECUTION_MODE, 'live');
          assert.equal(env.VERA_DEEPSEEK_LIVE_ENABLED, 'true');
          assert.equal(env.VERA_DEEPSEEK_ADAPTER_SHA256, task.adapter_sha256);
          assert.equal(env.VERA_DEEPSEEK_MANIFEST_SHA256, digest(raw));
          assert.equal(env.GITHUB_TOKEN, undefined);
          assert.equal(env.DEEPSEEK_API_KEY, undefined);
          assert.equal(existsSync(env.VERA_DEEPSEEK_RECEIPT), false);
          mkdirSync(join(receiptRoot, 'issue-421'), { mode: 0o700 });
          writeFileSync(env.VERA_DEEPSEEK_RECEIPT, JSON.stringify({ state: 'controller-owned', retained: true }), { mode: 0o600 });
          return scenario === 'uncertain' ? { status: null, error: { code: 'ETIMEDOUT' } } : { status: 0 };
        }
      };
      if (['host-refused', 'live-read-timeout', 'main-read-timeout'].includes(scenario)) {
        let cursorWrites = 0;
        await assert.rejects(pollOnce({ read: () => 320, readCreatedAt: () => comment.created_at,
          list: async () => [comment], processComment: event => processDispatchComment(event, options),
          write: () => { cursorWrites += 1; } }));
        assert.equal(cursorWrites, 0);
        assert.equal(calls, 0);
        assert.equal(existsSync(join(receiptRoot, 'issue-421')), false);
        continue;
      }
      const expected = scenario === 'success' ? 'worker-returned' : scenario === 'uncertain' ? 'uncertain-or-failed' : 'refused';
      assert.deepEqual(await processDispatchComment(comment, options), { state: expected }, scenario);
      assert.equal(calls, ['success', 'uncertain'].includes(scenario) ? 1 : 0, scenario);
      if (calls) {
        assert.deepEqual(JSON.parse(readFileSync(join(receiptRoot, 'issue-421/receipt.json'), 'utf8')),
          { state: 'controller-owned', retained: true });
        // Duplicate classification follows all freshness checks and makes no second adapter call.
        options.preflight = () => {};
        assert.deepEqual(await processDispatchComment(comment, options), { state: 'duplicate' });
        assert.equal(calls, 1);
      }
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  }
});
