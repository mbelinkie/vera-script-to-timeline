import test from 'node:test';
import assert from 'node:assert/strict';
import { issueRevision } from './chat-review-current.mjs';
import { qualityApprovalMetadata, verifyQualityApproval, main } from './deepseek-quality-gate.mjs';

const identity = { issue: 999, manifestSha: 'a'.repeat(64), sourceSha: 'b'.repeat(40),
  episodeIndex: 1, target: 'scripts/fixtures/deepseek-quality/prefix/target.py' };
const metadata = qualityApprovalMetadata(identity);

function fixture() {
  const issue = {
    number: 999, title: 'Synthetic calibration only', state: 'open', comments: 1,
    repository_url: 'https://api.github.com/repos/mbelinkie/vera-script-to-timeline',
    html_url: 'https://github.com/mbelinkie/vera-script-to-timeline/issues/999',
    updated_at: '2026-11-02T19:00:00Z',
    labels: ['type:implementation', 'chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'],
    body: '## DeepSeek Handoff\nLocal, bounded calibration.\n<!-- VERA_DEEPSEEK_QUALITY_V1 ' + JSON.stringify(metadata) + ' -->'
  };
  const approval = {
    id: 1, user: { login: 'mbelinkie' }, performed_via_github_app: null,
    created_at: '2026-11-02T19:00:00Z', updated_at: '2026-11-02T19:00:00Z',
    body: '<!-- VERA_CHAT_REVIEW_V1 ' + JSON.stringify({ revision: issueRevision(issue.title, issue.body),
      producer: 'mbelinkie', reviewedAt: '2026-11-02T19:00:00.000Z', promptVersion: '1' }) + ' -->'
  };
  return { issue, approval };
}

function reader({ issue, approval }, mutate = () => {}) {
  let reads = 0;
  return args => {
    assert.equal(args[0], 'api');
    assert.match(args.at(-1), /^repos\/mbelinkie\/vera-script-to-timeline\/issues\/999(?:\/comments\?per_page=100)?$/);
    if (args.includes('--paginate')) return JSON.stringify([[approval]]);
    const current = JSON.parse(JSON.stringify(issue));
    mutate(current, ++reads);
    return JSON.stringify(current);
  };
}

test('accepts exact current canonical approval and bounded calibration identity', () => {
  const result = verifyQualityApproval(reader(fixture()), identity);
  assert.equal(result.approved, true);
  assert.equal(result.reviewCommentId, 1);
  assert.equal(result.taskCapUsd, '0.80');
  assert.equal(result.campaignCapUsd, '2.40');
  assert.equal(result.manifestSha256, identity.manifestSha);
  assert.deepEqual(result.verifiedRates, metadata.verifiedRates);
});

test('rejects changed manifests, source, index, target and malformed CLI arguments', () => {
  for (const altered of [
    { manifestSha: 'c'.repeat(64) }, { sourceSha: 'c'.repeat(40) }, { episodeIndex: 2 },
    { target: '../private.py' }, { issue: 0 }
  ]) assert.throws(() => verifyQualityApproval(reader(fixture()), { ...identity, ...altered }));
  for (const argv of [[], ['999', identity.manifestSha, identity.sourceSha, '4', identity.target],
    ['999;touch x', identity.manifestSha, identity.sourceSha, '1', identity.target]]) {
    assert.throws(() => main(argv, reader(fixture())));
  }
});

test('rejects stale, edited, app-authored and missing approval', () => {
  for (const change of [
    value => { value.issue.body += '\nChanged task.'; },
    value => { value.approval.updated_at = '2026-11-02T19:00:01Z'; },
    value => { value.approval.performed_via_github_app = { id: 1 }; },
    value => { value.approval.user.login = 'other'; }
  ]) {
    const value = fixture(); change(value);
    assert.throws(() => verifyQualityApproval(reader(value), identity));
  }
});

test('rejects removal of eligibility or a concurrent body/label change', () => {
  for (const change of [
    current => { current.labels = current.labels.filter(label => label !== 'deepseek-ready'); },
    current => { current.labels.push('owner:codex'); },
    current => { current.labels.push('chat-review-pending'); },
    current => { current.state = 'closed'; },
    current => { current.body += '\nChanged task.'; }
  ]) assert.throws(() => verifyQualityApproval(reader(fixture(), (current, count) => {
    if (count === 4) change(current);
  }), identity));
});

test('rejects duplicate metadata, extra fields and a larger authorized cap', () => {
  for (const alter of [
    body => body + '\n<!-- VERA_DEEPSEEK_QUALITY_V1 ' + JSON.stringify(metadata) + ' -->',
    body => body.replace('"taskCapUsd":"0.80"', '"taskCapUsd":"8.00"'),
    body => body.replace('"effort":"high"', '"effort":"high","extra":true')
  ]) {
    const value = fixture(); value.issue.body = alter(value.issue.body);
    assert.throws(() => verifyQualityApproval(reader(value), identity));
  }
  const value = fixture();
  value.issue.body = value.issue.body.replace('peak_output_usd_per_million":"3.96',
    'peak_output_usd_per_million":"3.97');
  assert.throws(() => verifyQualityApproval(reader(value), identity));
});
