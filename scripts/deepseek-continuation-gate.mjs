// Read-only authorization for one separately approved DeepSeek continuation.
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyReviewFromGh } from './chat-review-github.mjs';
import { readPublicGh as readIssueGh } from './deepseek-receiver.mjs';
import { REPO, RESEARCH_REPO, requireDispatchRepo, verifyCurrentIssue } from './deepseek-dispatch.mjs';

const MARKER = '<!-- VERA_DEEPSEEK_CONTINUATION_V1 ';
const IDENTITY_KEYS = [
  'issue', 'commentId', 'manifestSha', 'sourceSha', 'adapterSha',
  'reconciliationSha', 'attemptId', 'campaign', 'model', 'maxOutputTokens'
].sort();
const MODELS = new Set(['deepseek-v4-pro', 'deepseek-flash']);
const VERIFIED_RATES = {
  'deepseek-v4-pro': {
    peak_cache_hit_usd_per_million: '0.044',
    peak_cache_miss_usd_per_million: '1.32',
    peak_output_usd_per_million: '3.96'
  },
  'deepseek-flash': {
    peak_cache_hit_usd_per_million: '0.006',
    peak_cache_miss_usd_per_million: '0.30',
    peak_output_usd_per_million: '1.20'
  }
};

function validateIdentity(identity, { live = false } = {}) {
  if (!identity || typeof identity !== 'object' || Array.isArray(identity) ||
      Object.getPrototypeOf(identity) !== Object.prototype) {
    throw new Error('Invalid approval identity');
  }
  const hasRepository = Object.hasOwn(identity, 'repository');
  if (hasRepository && !live) throw new Error('Invalid continuation identity');
  const keys = Reflect.ownKeys(identity);
  const expectedKeys = hasRepository ? [...IDENTITY_KEYS, 'repository'].sort() : IDENTITY_KEYS;
  if (keys.some(key => typeof key !== 'string') || keys.length !== expectedKeys.length ||
      keys.sort().some((key, index) => key !== expectedKeys[index])) {
    throw new Error('Invalid approval identity');
  }
  const repository = hasRepository ? identity.repository : REPO;
  const repoSlug = requireDispatchRepo(repository);
  if (hasRepository && repository !== RESEARCH_REPO) {
    throw new Error('Only Research live identities bind an explicit repository');
  }
  if (!Number.isSafeInteger(identity.issue) || identity.issue < 1 ||
      !Number.isSafeInteger(identity.commentId) || identity.commentId < 1 ||
      !/^[a-f0-9]{64}$/.test(identity.manifestSha || '') ||
      !/^[a-f0-9]{40}$/.test(identity.sourceSha || '') ||
      !/^[a-f0-9]{64}$/.test(identity.adapterSha || '') ||
      !/^[a-f0-9]{64}$/.test(identity.reconciliationSha || '') ||
      !/^[a-z0-9][a-z0-9-]{7,63}$/.test(identity.attemptId || '') ||
      !/^[a-z0-9][a-z0-9-]{7,63}$/.test(identity.campaign || '') ||
      !MODELS.has(identity.model) ||
      !Number.isSafeInteger(identity.maxOutputTokens) ||
      identity.maxOutputTokens < 512 || identity.maxOutputTokens > 24000) {
    throw new Error('Invalid approval identity');
  }
  if ((repository === REPO && identity.issue === 411) || identity.campaign === 'quality-2026-11-02-v1') {
    throw new Error('Legacy approval identity is not eligible');
  }
  return { identity, repository, repoSlug, hasRepository };
}

function baseApprovalMetadata(identity) {
  return {
    attemptId: identity.attemptId,
    campaign: identity.campaign,
    manifestSha256: identity.manifestSha,
    sourceSha: identity.sourceSha,
    adapterSha256: identity.adapterSha,
    reconciliationSha256: identity.reconciliationSha,
    model: identity.model,
    maxOutputTokens: identity.maxOutputTokens,
    maxInputUnits: 20000,
    taskCapUsd: '0.25',
    campaignCapUsd: '0.25',
    lifetimeCapUsd: '10',
    effort: 'high',
    verifiedRates: { [identity.model]: { ...VERIFIED_RATES[identity.model] } }
  };
}

export function continuationApprovalMetadata(identity) {
  validateIdentity(identity);
  return baseApprovalMetadata(identity);
}

export function liveBaseApprovalMetadata(identity) {
  const validated = validateIdentity(identity, { live: true });
  return baseApprovalMetadata(validated.identity);
}

function exactJson(actual, expected) {
  if (actual === expected) return true;
  if (!actual || !expected || typeof actual !== 'object' || typeof expected !== 'object' ||
      Array.isArray(actual) !== Array.isArray(expected)) return false;
  if (Array.isArray(actual)) {
    return actual.length === expected.length && actual.every((value, index) => exactJson(value, expected[index]));
  }
  const actualKeys = Reflect.ownKeys(actual);
  const expectedKeys = Reflect.ownKeys(expected);
  return actualKeys.length === expectedKeys.length && actualKeys.every(key =>
    typeof key === 'string' && Object.hasOwn(expected, key) && exactJson(actual[key], expected[key]));
}

function issueSnapshot(issue) {
  // One comment page per canonical history keeps public verification within ten reads.
  if (!issue || typeof issue !== 'object' || typeof issue.title !== 'string' ||
      typeof issue.body !== 'string' || typeof issue.updated_at !== 'string' ||
      !Number.isSafeInteger(issue.comments) || issue.comments < 0 || issue.comments > 100 ||
      !Array.isArray(issue.labels)) throw new Error('Invalid continuation issue snapshot');
  const labels = issue.labels.map(label => typeof label === 'string' ? label : label?.name);
  if (labels.some(label => typeof label !== 'string' || !label)) {
    throw new Error('Invalid continuation issue labels');
  }
  return JSON.stringify({
    number: issue.number, repository_url: issue.repository_url, html_url: issue.html_url,
    title: issue.title, body: issue.body, state: issue.state,
    pull_request: Boolean(issue.pull_request), comments: issue.comments,
    updated_at: issue.updated_at, labels: labels.sort()
  });
}

function verifyIssueMetadata(issue, expected, marker, markerName, action) {
  const markerStarts = [...issue.body.matchAll(new RegExp('<!--\\s*' + markerName + '\\b', 'g'))];
  const markers = [...issue.body.matchAll(new RegExp('<!-- ' + markerName + ' (\\{[^\\r\\n]*\\}) -->', 'g'))];
  if (markerStarts.length !== 1 || markers.length !== 1 || issue.body.split(marker).length !== 2) {
    throw new Error(action + ' approval marker missing or duplicated');
  }
  let actual;
  try { actual = JSON.parse(markers[0][1]); }
  catch { throw new Error(action + ' approval metadata is invalid'); }
  if (!exactJson(actual, expected)) throw new Error(action + ' approval metadata differs');
}

function canonicalRestTimestamp(value) {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) return false;
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return false;
  const canonical = new Date(timestamp).toISOString();
  return value === canonical || value === canonical.replace('.000Z', 'Z');
}

function findApprovalComment(comments, commentId, action) {
  const matches = comments.filter(comment => comment.id === commentId);
  if (matches.length !== 1) throw new Error(action + ' request comment missing or duplicated');
  return matches[0];
}

function verifyApprovalComment(comment, repository, issueNumber, command, action) {
  const issueUrl = 'https://api.github.com/repos/' + repository + '/issues/' + issueNumber;
  if (comment.body !== command ||
      comment.issue_url !== issueUrl || comment.user.login !== 'mbelinkie' ||
      comment.performed_via_github_app !== null || !canonicalRestTimestamp(comment.created_at) ||
      comment.created_at !== comment.updated_at) {
    throw new Error(action + ' request comment changed or is not authorized');
  }
  return comment;
}

function verifyIssueRepository(issue, repository, issueNumber) {
  if (issue?.number !== issueNumber ||
      issue.repository_url !== 'https://api.github.com/repos/' + repository ||
      issue.html_url !== 'https://github.com/' + repository + '/issues/' + issueNumber) {
    throw new Error('Approval issue repository identity mismatch');
  }
}

function repoPath(repoSlug) {
  return `repos/mbelinkie/${repoSlug}`;
}

function readIssue(readGh, repoSlug, number) {
  return JSON.parse(readGh(['api', `${repoPath(repoSlug)}/issues/${number}`]));
}

function currentMainSha(readGh, repoSlug) {
  const ref = JSON.parse(readGh(['api', `${repoPath(repoSlug)}/git/ref/heads/main`]));
  if (ref?.ref !== 'refs/heads/main' || ref.object?.type !== 'commit' ||
      !/^[a-f0-9]{40}$/.test(ref.object.sha || '')) {
    throw new Error('Current main ref is unavailable');
  }
  return ref.object.sha;
}

function verifyReviewWithHistory(readGh, repository, repoSlug, issueNumber, issue) {
  const issuePath = `${repoPath(repoSlug)}/issues/${issueNumber}`;
  const historyPath = `${issuePath}/comments?per_page=100`;
  const histories = [];
  const review = verifyReviewFromGh(args => {
    const result = readGh(args);
    if (args[0] === 'api' && args.at(-1) === issuePath) issueSnapshot(JSON.parse(result));
    if (args[0] === 'api' && args.includes('--paginate') && args.includes('--slurp') &&
        args.at(-1) === historyPath) histories.push(result);
    return result;
  }, repository, issueNumber, issue);
  if (histories.length !== 2) throw new Error('Producer review history was not verified twice');
  const pages = JSON.parse(histories[1]);
  if (!Array.isArray(pages) || !pages.every(Array.isArray)) {
    throw new Error('Producer review history is invalid');
  }
  return { review, comments: pages.flat() };
}

export function verifyPublicApproval(readGh, identity, mode) {
  if (typeof readGh !== 'function') throw new Error('Public GitHub reader required');
  const repoIdentity = validateIdentity(identity, { live: mode === 'live' });
  const { repository, repoSlug, hasRepository } = repoIdentity;
  const readRepositoryGh = hasRepository
    ? args => readGh(args, undefined, { repository })
    : readGh;
  let configuration;
  if (mode === 'continuation') {
    configuration = {
      metadata: continuationApprovalMetadata,
      marker: MARKER,
      markerName: 'VERA_DEEPSEEK_CONTINUATION_V1',
      action: 'Continuation',
      command: '/deepseek continue'
    };
  } else if (mode === 'live') {
    configuration = {
      metadata: identity => ({
        ...liveBaseApprovalMetadata(identity),
        ...(hasRepository ? { repository } : {}),
        executionMode: 'live',
        transportContract: 'VERA_DEEPSEEK_RECEIVER_V2'
      }),
      marker: '<!-- VERA_DEEPSEEK_LIVE_V2 ',
      markerName: 'VERA_DEEPSEEK_LIVE_V2',
      action: 'Live',
      command: '/deepseek dispatch'
    };
  } else {
    throw new Error('Unknown public approval mode');
  }
  const expected = configuration.metadata(identity);
  const issue = readIssue(readRepositoryGh, repoSlug, identity.issue);
  verifyIssueRepository(issue, repository, identity.issue);
  verifyCurrentIssue(issue, identity.issue, { repository });
  const before = issueSnapshot(issue);
  verifyIssueMetadata(issue, expected, configuration.marker, configuration.markerName, configuration.action);

  const mainBefore = currentMainSha(readRepositoryGh, repoSlug);
  if (mainBefore !== identity.sourceSha) throw new Error('Approved source is not current main');

  const { review, comments } = verifyReviewWithHistory(readRepositoryGh, repository, repoSlug, identity.issue, issue);
  verifyApprovalComment(
    findApprovalComment(comments, identity.commentId, configuration.action),
    repository,
    identity.issue,
    configuration.command,
    configuration.action
  );

  const currentIssue = readIssue(readRepositoryGh, repoSlug, identity.issue);
  verifyIssueRepository(currentIssue, repository, identity.issue);
  verifyCurrentIssue(currentIssue, identity.issue, { repository });
  const after = issueSnapshot(currentIssue);
  const mainAfter = currentMainSha(readRepositoryGh, repoSlug);
  if (before !== after || mainAfter !== identity.sourceSha || mainAfter !== mainBefore) {
    throw new Error(configuration.action + ' authorization changed during verification');
  }

  return {
    approved: true,
    issue: identity.issue,
    commentId: identity.commentId,
    ...expected,
    reviewCommentId: review.commentId,
    revision: review.revision
  };
}

export function verifyContinuationApproval(readGh, identity) {
  return verifyPublicApproval(readGh, identity, 'continuation');
}

function readPublicMainRef(args, spawn, expectedRepository) {
  if (args.length !== 2 || args[0] !== 'api' || typeof args[1] !== 'string') {
    throw new Error('Unsupported public main read');
  }
  const match = args[1].match(/^repos\/([^/]+)\/([^/]+)\/git\/ref\/heads\/main$/);
  const repository = match && `${match[1]}/${match[2]}`;
  if (!match || (expectedRepository !== undefined && expectedRepository !== repository) ||
      args[1] !== `repos/${match[1]}/${requireDispatchRepo(repository)}/git/ref/heads/main`) {
    throw new Error('Unsupported public main read');
  }
  const route = args[1];
  const result = spawn('curl', [
    '--disable', '--fail', '--silent', '--show-error', '--max-time', '15', '--proto', '=https',
    '--header', 'Accept: application/vnd.github+json', '--header', 'X-GitHub-Api-Version: 2022-11-28',
    '--header', 'User-Agent: vera-deepseek-approval-gate', `https://api.github.com/${route}`
  ], {
    encoding: 'utf8', maxBuffer: 1024 * 1024, shell: false,
    env: { PATH: process.env.PATH || '/usr/bin:/bin' }
  });
  if (result.error || result.signal || result.status !== 0) throw new Error('Public main ref read failed');
  return result.stdout;
}

export function readPublicGh(args, spawn = spawnSync, options = {}) {
  if (typeof args?.at(-1) === 'string' && /\/git\/ref\/heads\/main$/.test(args.at(-1))) {
    return readPublicMainRef(args, spawn, options.repository);
  }
  return readIssueGh(args, spawn, options);
}

export function main(argv = process.argv.slice(2), readGh = readPublicGh) {
  if (argv.length !== 1 || typeof argv[0] !== 'string') {
    throw new Error('Expected one continuation identity JSON argument');
  }
  let identity;
  try { identity = JSON.parse(argv[0]); }
  catch { throw new Error('Expected one continuation identity JSON argument'); }
  return verifyContinuationApproval(readGh, identity);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    console.log(JSON.stringify(main()));
  } catch {
    console.error('Continuation approval refused; no provider request was made.');
    process.exitCode = 1;
  }
}
