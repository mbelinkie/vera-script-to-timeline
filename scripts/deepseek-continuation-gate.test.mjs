import test from 'node:test';
import assert from 'node:assert/strict';
import { issueRevision } from './chat-review-current.mjs';
import {
  continuationApprovalMetadata, verifyContinuationApproval, main
} from './deepseek-continuation-gate.mjs';

const REPO = 'mbelinkie/vera-script-to-timeline';
const identity = {
  issue: 415,
  commentId: 2,
  manifestSha: 'a'.repeat(64),
  sourceSha: 'b'.repeat(40),
  adapterSha: 'c'.repeat(64),
  reconciliationSha: 'd'.repeat(64),
  attemptId: 'attempt-2026-11-03',
  campaign: 'continuation-2026-11-03',
  model: 'deepseek-v4-pro',
  maxOutputTokens: 4096
};

function approval(issue, overrides = {}) {
  return {
    id: 1,
    issue_url: `https://api.github.com/repos/${REPO}/issues/${identity.issue}`,
    user: { login: 'mbelinkie' },
    performed_via_github_app: null,
    created_at: '2026-11-03T14:00:00Z',
    updated_at: '2026-11-03T14:00:00Z',
    body: '<!-- VERA_CHAT_REVIEW_V1 ' + JSON.stringify({
      revision: issueRevision(issue.title, issue.body),
      producer: 'mbelinkie', reviewedAt: '2026-11-03T14:00:00.000Z', promptVersion: '1'
    }) + ' -->',
    ...overrides
  };
}

function fixture({ metadata = continuationApprovalMetadata(identity), event = {}, review = {},
  omitEvent = false, omitReview = false } = {}) {
  const issue = {
    number: identity.issue,
    title: 'One bounded continuation trial',
    state: 'open',
    comments: 2,
    repository_url: `https://api.github.com/repos/${REPO}`,
    html_url: `https://github.com/${REPO}/issues/${identity.issue}`,
    updated_at: '2026-11-03T14:01:00Z',
    labels: ['type:implementation', 'chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'],
    body: '## DeepSeek Handoff\nOne bounded, separately approved continuation.\n' +
      '<!-- VERA_DEEPSEEK_CONTINUATION_V1 ' + JSON.stringify(metadata) + ' -->'
  };
  const reviewComment = approval(issue, review);
  const continuation = {
    id: identity.commentId,
    body: '/deepseek continue',
    issue_url: `https://api.github.com/repos/${REPO}/issues/${identity.issue}`,
    user: { login: 'mbelinkie' },
    performed_via_github_app: null,
    created_at: '2026-11-03T14:01:00Z',
    updated_at: '2026-11-03T14:01:00Z',
    ...event
  };
  const comments = [];
  if (!omitReview) comments.push(reviewComment);
  if (!omitEvent) comments.push(continuation);
  comments.sort((left, right) => left.id - right.id);
  issue.comments = comments.length;
  return { issue, comments, mainSha: identity.sourceSha };
}

function reader(state, mutate = () => {}) {
  const counts = { issue: 0, history: 0, main: 0 };
  return args => {
    assert.equal(args[0], 'api');
    const route = args.at(-1);
    if (route === `repos/${REPO}/issues/${identity.issue}`) {
      mutate(state, 'issue', ++counts.issue);
      return JSON.stringify(globalThis.structuredClone(state.issue));
    }
    if (route === `repos/${REPO}/issues/${identity.issue}/comments?per_page=100`) {
      assert.ok(args.includes('--paginate') && args.includes('--slurp'));
      mutate(state, 'history', ++counts.history);
      return JSON.stringify([globalThis.structuredClone(state.comments)]);
    }
    if (route === `repos/${REPO}/git/ref/heads/main`) {
      mutate(state, 'main', ++counts.main);
      return JSON.stringify({ ref: 'refs/heads/main', object: { type: 'commit', sha: state.mainSha } });
    }
    assert.fail(`Unexpected public read: ${route}`);
  };
}

function approve(state = fixture(), mutate) {
  return verifyContinuationApproval(reader(state, mutate), identity);
}

test('builds exact bounded metadata with only the selected current quality rates', () => {
  const pro = continuationApprovalMetadata(identity);
  assert.deepEqual(pro, {
    attemptId: identity.attemptId,
    campaign: identity.campaign,
    manifestSha256: identity.manifestSha,
    sourceSha: identity.sourceSha,
    adapterSha256: identity.adapterSha,
    reconciliationSha256: identity.reconciliationSha,
    model: 'deepseek-v4-pro',
    maxOutputTokens: 4096,
    maxInputUnits: 20000,
    taskCapUsd: '0.25',
    campaignCapUsd: '0.25',
    lifetimeCapUsd: '10',
    effort: 'high',
    verifiedRates: {
      'deepseek-v4-pro': {
        peak_cache_hit_usd_per_million: '0.044',
        peak_cache_miss_usd_per_million: '1.32',
        peak_output_usd_per_million: '3.96'
      }
    }
  });
  const flash = continuationApprovalMetadata({ ...identity, model: 'deepseek-flash' });
  assert.deepEqual(flash.verifiedRates, {
    'deepseek-flash': {
      peak_cache_hit_usd_per_million: '0.006',
      peak_cache_miss_usd_per_million: '0.30',
      peak_output_usd_per_million: '1.20'
    }
  });
});

test('accepts a current Producer approval and exact continuation comment with either comment ID order', () => {
  const result = approve();
  assert.equal(result.approved, true);
  assert.equal(result.issue, identity.issue);
  assert.equal(result.commentId, identity.commentId);
  assert.equal(result.reviewCommentId, 1);
  assert.equal(result.sourceSha, identity.sourceSha);
  assert.equal(result.taskCapUsd, '0.25');
  assert.deepEqual(Object.keys(result.verifiedRates), ['deepseek-v4-pro']);

  const eventFirst = fixture({ event: {
    id: 1, created_at: '2026-11-03T13:59:00Z', updated_at: '2026-11-03T13:59:00Z'
  }, review: { id: 2 } });
  const eventFirstResult = verifyContinuationApproval(reader(eventFirst), { ...identity, commentId: 1 });
  assert.equal(eventFirstResult.approved, true);
  assert.equal(eventFirstResult.commentId, 1);
  assert.equal(eventFirstResult.reviewCommentId, 2);
});

test('rejects invalid identities, issue 411, the quality campaign and extra CLI keys', () => {
  for (const altered of [
    { issue: 0 }, { issue: 411 }, { commentId: 0 }, { manifestSha: 'A'.repeat(64) },
    { sourceSha: 'b'.repeat(39) }, { adapterSha: 'z'.repeat(64) },
    { reconciliationSha: 'd'.repeat(63) }, { attemptId: 'short' },
    { campaign: 'quality-2026-11-02-v1' }, { model: 'deepseek-v4-pro-preview' },
    { maxOutputTokens: 511 }, { maxOutputTokens: 24001 }, { maxOutputTokens: 512.5 }
  ]) assert.throws(() => continuationApprovalMetadata({ ...identity, ...altered }));
  assert.throws(() => continuationApprovalMetadata({ ...identity, extra: true }));
  assert.throws(() => main([], reader(fixture())));
  assert.throws(() => main(['not-json'], reader(fixture())));
  assert.throws(() => main([JSON.stringify({ ...identity, extra: true })], reader(fixture())));
  assert.throws(() => main([JSON.stringify(identity), 'extra'], reader(fixture())));
});

test('rejects missing or stale Producer review and missing continuation event', () => {
  assert.throws(() => approve(fixture({ omitReview: true })));
  assert.throws(() => approve(fixture({ omitEvent: true })));

  const stale = fixture();
  stale.issue.body += '\nChanged task.';
  assert.throws(() => approve(stale));

  for (const review of [
    { updated_at: '2026-11-03T14:00:01Z' },
    { performed_via_github_app: { id: 7 } },
    { user: { login: 'someone-else' } }
  ]) assert.throws(() => approve(fixture({ review })));
});

test('rejects an edited, app-authored, wrong-ID, wrong-actor or wrong-issue continuation comment', () => {
  for (const event of [
    { body: '/deepseek continue\n' },
    { updated_at: '2026-11-03T14:01:01Z' },
    { performed_via_github_app: { id: 7 } },
    { user: { login: 'someone-else' } },
    { issue_url: `https://api.github.com/repos/${REPO}/issues/999` },
    { created_at: 'not-a-canonical-time', updated_at: 'not-a-canonical-time' }
  ]) assert.throws(() => approve(fixture({ event })));

  assert.throws(() => verifyContinuationApproval(reader(fixture()), { ...identity, commentId: 3 }));
  assert.throws(() => verifyContinuationApproval(reader(fixture()), { ...identity, commentId: 1 }));
});

test('rejects changes to approved hashes, model, output budget, caps, rates and marker shape', () => {
  const alterations = [
    metadata => { metadata.manifestSha256 = 'e'.repeat(64); },
    metadata => { metadata.sourceSha = 'f'.repeat(40); },
    metadata => { metadata.adapterSha = 'e'.repeat(64); },
    metadata => { metadata.reconciliationSha256 = 'e'.repeat(64); },
    metadata => { metadata.model = 'deepseek-flash'; },
    metadata => { metadata.maxOutputTokens = 8192; },
    metadata => { metadata.taskCapUsd = '0.26'; },
    metadata => { metadata.campaignCapUsd = '0.26'; },
    metadata => { metadata.lifetimeCapUsd = '11'; },
    metadata => { metadata.verifiedRates['deepseek-v4-pro'].peak_output_usd_per_million = '3.97'; },
    metadata => { metadata.extra = true; }
  ];
  for (const alter of alterations) {
    const metadata = globalThis.structuredClone(continuationApprovalMetadata(identity));
    alter(metadata);
    assert.throws(() => approve(fixture({ metadata })));
  }

  const duplicate = fixture();
  duplicate.issue.body += '\n' + duplicate.issue.body.match(/<!-- VERA_DEEPSEEK_CONTINUATION_V1 .* -->/)[0];
  assert.throws(() => approve(duplicate));
});

test('rejects a source revision that is not current main', () => {
  const state = fixture();
  state.mainSha = 'e'.repeat(40);
  assert.throws(() => approve(state));
});

test('detects issue, comment history and main ref changes during verification', () => {
  assert.throws(() => approve(fixture(), (state, kind, count) => {
    if (kind === 'issue' && count === 6) state.issue.body += '\nChanged during verification.';
  }));
  assert.throws(() => approve(fixture(), (state, kind, count) => {
    if (kind === 'history' && count === 6) state.comments[1].body = '/deepseek continue edited';
  }));
  assert.throws(() => approve(fixture(), (state, kind, count) => {
    if (kind === 'main' && count === 2) state.mainSha = 'e'.repeat(40);
  }));
});

test('CLI accepts one serialized identity and returns a read-only approval result', () => {
  const result = main([JSON.stringify(identity)], reader(fixture()));
  assert.equal(result.approved, true);
  assert.equal(result.reviewCommentId, 1);
});
