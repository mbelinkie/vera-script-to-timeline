import test from 'node:test';
import assert from 'node:assert/strict';
import { issueRevision } from './chat-review-current.mjs';
import { continuationApprovalMetadata, readPublicGh as continuationReadPublicGh } from './deepseek-continuation-gate.mjs';
import {
  liveApprovalMetadata, main, readPublicGh, verifyLiveApproval
} from './deepseek-live-gate.mjs';

const REPO = 'mbelinkie/vera-script-to-timeline';
const MARKER = '<!-- VERA_DEEPSEEK_LIVE_V2 ';
const identity = {
  issue: 416,
  commentId: 2,
  manifestSha: 'a'.repeat(64),
  sourceSha: 'b'.repeat(40),
  adapterSha: 'c'.repeat(64),
  reconciliationSha: 'd'.repeat(64),
  attemptId: 'live-attempt-2026-11-03',
  campaign: 'live-campaign-2026-11-03',
  model: 'deepseek-v4-pro',
  maxOutputTokens: 4096
};

function issueBody(metadata) {
  return '## DeepSeek Handoff\nOne bounded live receiver action.\n' +
    MARKER + JSON.stringify(metadata) + ' -->';
}

function reviewComment(issue, overrides = {}) {
  return {
    id: 1,
    user: { login: 'mbelinkie' },
    performed_via_github_app: null,
    created_at: '2026-11-03T14:00:00Z',
    updated_at: '2026-11-03T14:00:00Z',
    body: '<!-- VERA_CHAT_REVIEW_V1 ' + JSON.stringify({
      revision: issueRevision(issue.title, issue.body),
      producer: 'mbelinkie',
      reviewedAt: '2026-11-03T14:00:00.000Z',
      promptVersion: '1'
    }) + ' -->',
    ...overrides
  };
}

function fixture({
  metadata = liveApprovalMetadata(identity),
  event = {},
  review = {},
  omitEvent = false,
  omitReview = false
} = {}) {
  const issue = {
    number: identity.issue,
    title: 'One separately approved live receiver action',
    state: 'open',
    comments: 2,
    repository_url: 'https://api.github.com/repos/' + REPO,
    html_url: 'https://github.com/' + REPO + '/issues/' + identity.issue,
    updated_at: '2026-11-03T14:01:00Z',
    labels: ['type:implementation', 'chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'],
    body: issueBody(metadata)
  };
  const reviewApproval = reviewComment(issue, review);
  const dispatch = {
    id: identity.commentId,
    body: '/deepseek dispatch',
    issue_url: 'https://api.github.com/repos/' + REPO + '/issues/' + identity.issue,
    user: { login: 'mbelinkie' },
    performed_via_github_app: null,
    created_at: '2026-11-03T14:01:00Z',
    updated_at: '2026-11-03T14:01:00Z',
    ...event
  };
  const comments = [];
  if (!omitReview) comments.push(reviewApproval);
  if (!omitEvent) comments.push(dispatch);
  comments.sort((left, right) => left.id - right.id);
  issue.comments = comments.length;
  return { issue, comments, mainSha: identity.sourceSha };
}

function reader(state, mutate = () => {}) {
  const counts = { issue: 0, history: 0, main: 0 };
  const read = args => {
    assert.equal(args[0], 'api');
    const route = args.at(-1);
    if (route === 'repos/' + REPO + '/issues/' + identity.issue) {
      mutate(state, 'issue', ++counts.issue);
      return JSON.stringify(globalThis.structuredClone(state.issue));
    }
    if (route === 'repos/' + REPO + '/issues/' + identity.issue + '/comments?per_page=100') {
      assert.ok(args.includes('--paginate') && args.includes('--slurp'));
      mutate(state, 'history', ++counts.history);
      return JSON.stringify([globalThis.structuredClone(state.comments)]);
    }
    if (route === 'repos/' + REPO + '/git/ref/heads/main') {
      mutate(state, 'main', ++counts.main);
      return JSON.stringify({
        ref: 'refs/heads/main',
        object: { type: 'commit', sha: state.mainSha }
      });
    }
    assert.fail('Unexpected public read: ' + route);
  };
  return read;
}

function approve(state = fixture(), mutate) {
  return verifyLiveApproval(reader(state, mutate), identity);
}

function replaceReviewForCurrentIssue(state) {
  state.comments[0] = reviewComment(state.issue, { id: state.comments[0].id });
}

test('adds explicit live mode and receiver transport to the exact bounded continuation metadata', () => {
  assert.deepEqual(liveApprovalMetadata(identity), {
    ...continuationApprovalMetadata(identity),
    executionMode: 'live',
    transportContract: 'VERA_DEEPSEEK_RECEIVER_V2'
  });
  assert.equal(readPublicGh, continuationReadPublicGh);
});

test('accepts a current live Producer approval and exact unedited owner dispatch', () => {
  const state = fixture();
  const result = approve(state);
  assert.equal(result.approved, true);
  assert.equal(result.issue, identity.issue);
  assert.equal(result.commentId, identity.commentId);
  assert.equal(result.reviewCommentId, 1);
  assert.equal(result.sourceSha, identity.sourceSha);
  assert.equal(result.executionMode, 'live');
  assert.equal(result.transportContract, 'VERA_DEEPSEEK_RECEIVER_V2');
  assert.equal(result.taskCapUsd, '0.25');
});

test('refuses revoked or stale canonical Producer review and a changed handoff task', () => {
  const revoked = fixture();
  revoked.comments[0].body = 'Review revoked.';
  assert.throws(() => approve(revoked));

  const stale = fixture();
  stale.issue.body += '\nThe approved task changed.';
  assert.throws(() => approve(stale));
});

test('refuses missing, edited, app-authored, wrong-owner, or wrong-issue dispatch events', () => {
  assert.throws(() => approve(fixture({ omitEvent: true })));
  for (const event of [
    { body: '/deepseek dispatch extra' },
    { updated_at: '2026-11-03T14:01:01Z' },
    { performed_via_github_app: { id: 7 } },
    { user: { login: 'someone-else' } },
    { issue_url: 'https://api.github.com/repos/' + REPO + '/issues/999' },
    { created_at: 'not-a-canonical-time', updated_at: 'not-a-canonical-time' }
  ]) assert.throws(() => approve(fixture({ event })));
});

test('rejects continuation and mock approvals, even when their task review is current', () => {
  const continuation = fixture();
  const oldMetadata = continuationApprovalMetadata(identity);
  continuation.issue.body = '## DeepSeek Handoff\nOne bounded continuation.\n' +
    '<!-- VERA_DEEPSEEK_CONTINUATION_V1 ' + JSON.stringify(oldMetadata) + ' -->';
  continuation.comments[1].body = '/deepseek continue';
  replaceReviewForCurrentIssue(continuation);
  assert.throws(() => approve(continuation));

  const mockMetadata = liveApprovalMetadata(identity);
  mockMetadata.executionMode = 'mock';
  const mock = fixture({ metadata: mockMetadata });
  assert.throws(() => approve(mock));
});

test('rejects changed manifest, source, build, attempt, campaign, model, and output identity', () => {
  const alterations = [
    { manifestSha: 'e'.repeat(64) },
    { sourceSha: 'f'.repeat(40) },
    { adapterSha: 'e'.repeat(64) },
    { reconciliationSha: 'f'.repeat(64) },
    { attemptId: 'changed-attempt-2026-11-03' },
    { campaign: 'changed-campaign-2026-11-03' },
    { model: 'deepseek-flash' },
    { maxOutputTokens: 8192 }
  ];
  for (const alteration of alterations) {
    const state = fixture();
    const changedIdentity = { ...identity, ...alteration };
    if (alteration.sourceSha) state.mainSha = alteration.sourceSha;
    assert.throws(() => verifyLiveApproval(reader(state), changedIdentity));
  }
  assert.throws(() => approve(fixture(), (state, kind, count) => {
    if (kind === 'main' && count === 2) state.mainSha = 'e'.repeat(40);
  }));
});

test('rejects changed mode, transport, limits, caps, rates, and extra metadata', () => {
  const changes = [
    metadata => { metadata.executionMode = 'mock'; },
    metadata => { metadata.executionMode = 'continuation'; },
    metadata => { metadata.transportContract = 'VERA_DEEPSEEK_MOCK_V1'; },
    metadata => { metadata.maxInputUnits = 20001; },
    metadata => { metadata.taskCapUsd = '0.26'; },
    metadata => { metadata.campaignCapUsd = '0.26'; },
    metadata => { metadata.lifetimeCapUsd = '11'; },
    metadata => { metadata.effort = 'medium'; },
    metadata => { metadata.verifiedRates['deepseek-v4-pro'].peak_cache_hit_usd_per_million = '0.045'; },
    metadata => { metadata.verifiedRates['deepseek-v4-pro'].peak_cache_miss_usd_per_million = '1.33'; },
    metadata => { metadata.verifiedRates['deepseek-v4-pro'].peak_output_usd_per_million = '3.97'; },
    metadata => { metadata.extra = true; }
  ];
  for (const change of changes) {
    const metadata = globalThis.structuredClone(liveApprovalMetadata(identity));
    change(metadata);
    assert.throws(() => approve(fixture({ metadata })));
  }

  const duplicate = fixture();
  duplicate.issue.body += '\n' + duplicate.issue.body.match(/<!-- VERA_DEEPSEEK_LIVE_V2 .* -->/)[0];
  replaceReviewForCurrentIssue(duplicate);
  assert.throws(() => approve(duplicate));
});

test('CLI accepts one serialized live identity and returns explicit live transport approval', () => {
  const result = main([JSON.stringify(identity)], reader(fixture()));
  assert.equal(result.approved, true);
  assert.equal(result.executionMode, 'live');
  assert.equal(result.transportContract, 'VERA_DEEPSEEK_RECEIVER_V2');
  assert.throws(() => main([], reader(fixture())));
  assert.throws(() => main(['not-json'], reader(fixture())));
});
