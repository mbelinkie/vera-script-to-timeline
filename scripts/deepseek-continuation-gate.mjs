// Read-only authorization for one separately approved DeepSeek continuation.
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyReviewFromGh } from './chat-review-github.mjs';
import { readPublicGh as readIssueGh } from './deepseek-receiver.mjs';
import { REPO, verifyCurrentIssue } from './deepseek-dispatch.mjs';

const MARKER = '<!-- VERA_DEEPSEEK_CONTINUATION_V1 ';
const MAIN_REF = `repos/${REPO}/git/ref/heads/main`;
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

function validateIdentity(identity) {
  if (!identity || typeof identity !== 'object' || Array.isArray(identity) ||
      Object.getPrototypeOf(identity) !== Object.prototype) {
    throw new Error('Invalid continuation identity');
  }
  const keys = Reflect.ownKeys(identity);
  if (keys.some(key => typeof key !== 'string') || keys.length !== IDENTITY_KEYS.length ||
      keys.sort().some((key, index) => key !== IDENTITY_KEYS[index])) {
    throw new Error('Invalid continuation identity');
  }
  if (!Number.isSafeInteger(identity.issue) || identity.issue < 1 || identity.issue === 411 ||
      !Number.isSafeInteger(identity.commentId) || identity.commentId < 1 ||
      !/^[a-f0-9]{64}$/.test(identity.manifestSha || '') ||
      !/^[a-f0-9]{40}$/.test(identity.sourceSha || '') ||
      !/^[a-f0-9]{64}$/.test(identity.adapterSha || '') ||
      !/^[a-f0-9]{64}$/.test(identity.reconciliationSha || '') ||
      !/^[a-z0-9][a-z0-9-]{7,63}$/.test(identity.attemptId || '') ||
      !/^[a-z0-9][a-z0-9-]{7,63}$/.test(identity.campaign || '') ||
      identity.campaign === 'quality-2026-11-02-v1' || !MODELS.has(identity.model) ||
      !Number.isSafeInteger(identity.maxOutputTokens) ||
      identity.maxOutputTokens < 512 || identity.maxOutputTokens > 24000) {
    throw new Error('Invalid continuation identity');
  }
  return identity;
}

export function continuationApprovalMetadata(identity) {
  validateIdentity(identity);
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
  if (!issue || typeof issue !== 'object' || typeof issue.title !== 'string' ||
      typeof issue.body !== 'string' || typeof issue.updated_at !== 'string' ||
      !Number.isSafeInteger(issue.comments) || issue.comments < 0 || issue.comments > 2000 ||
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

function verifyIssueMetadata(issue, expected) {
  const markerStarts = [...issue.body.matchAll(/<!--\s*VERA_DEEPSEEK_CONTINUATION_V1\b/g)];
  const markers = [...issue.body.matchAll(/<!-- VERA_DEEPSEEK_CONTINUATION_V1 (\{[^\r\n]*\}) -->/g)];
  if (markerStarts.length !== 1 || markers.length !== 1 || issue.body.split(MARKER).length !== 2) {
    throw new Error('Continuation approval marker missing or duplicated');
  }
  let actual;
  try { actual = JSON.parse(markers[0][1]); }
  catch { throw new Error('Continuation approval metadata is invalid'); }
  if (!exactJson(actual, expected)) throw new Error('Continuation approval metadata differs');
}

function canonicalRestTimestamp(value) {
  if (typeof value !== 'string' ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) return false;
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return false;
  const canonical = new Date(timestamp).toISOString();
  return value === canonical || value === canonical.replace('.000Z', 'Z');
}

function readComments(readGh, issue) {
  const path = `repos/${REPO}/issues/${issue.number}/comments?per_page=100`;
  const pages = JSON.parse(readGh(['api', '--paginate', '--slurp', path]));
  const count = issue.comments;
  const pageCount = Math.max(1, Math.ceil(count / 100));
  if (!Array.isArray(pages) || pages.length !== pageCount || !pages.every(Array.isArray)) {
    throw new Error('Continuation comment history is incomplete');
  }
  const comments = [];
  for (let pageIndex = 0; pageIndex < pageCount; pageIndex += 1) {
    const expectedLength = pageIndex === pageCount - 1 ? count - 100 * pageIndex : 100;
    if (pages[pageIndex].length !== expectedLength) throw new Error('Continuation comment history is incomplete');
    for (const comment of pages[pageIndex]) {
      if (!comment || typeof comment !== 'object' || Array.isArray(comment) ||
          !Number.isSafeInteger(comment.id) || comment.id < 1 || typeof comment.body !== 'string' ||
          typeof comment.issue_url !== 'string' || !comment.user || typeof comment.user.login !== 'string') {
        throw new Error('Continuation comment history is invalid');
      }
      comments.push(comment);
    }
  }
  return comments;
}

function findContinuationComment(comments, commentId) {
  const matches = comments.filter(comment => comment.id === commentId);
  if (matches.length !== 1) throw new Error('Continuation request comment missing or duplicated');
  return matches[0];
}

function verifyContinuationComment(comment, issueNumber, reviewCommentId) {
  const issueUrl = `https://api.github.com/repos/${REPO}/issues/${issueNumber}`;
  if (comment.id <= reviewCommentId || comment.body !== '/deepseek continue' ||
      comment.issue_url !== issueUrl || comment.user.login !== 'mbelinkie' ||
      comment.performed_via_github_app !== null || !canonicalRestTimestamp(comment.created_at) ||
      comment.created_at !== comment.updated_at) {
    throw new Error('Continuation request comment changed or is not authorized');
  }
  return comment;
}

function commentSnapshot(comment) {
  return JSON.stringify({
    id: comment.id, body: comment.body, issue_url: comment.issue_url,
    user: comment.user.login, created_at: comment.created_at,
    updated_at: comment.updated_at, performed_via_github_app: comment.performed_via_github_app
  });
}

function sameHistory(left, right) {
  return left.length === right.length && left.every((comment, index) =>
    commentSnapshot(comment) === commentSnapshot(right[index]));
}

function readIssue(readGh, number) {
  return JSON.parse(readGh(['api', `repos/${REPO}/issues/${number}`]));
}

function currentMainSha(readGh) {
  const ref = JSON.parse(readGh(['api', MAIN_REF]));
  if (ref?.ref !== 'refs/heads/main' || ref.object?.type !== 'commit' ||
      !/^[a-f0-9]{40}$/.test(ref.object.sha || '')) {
    throw new Error('Current main ref is unavailable');
  }
  return ref.object.sha;
}

export function verifyContinuationApproval(readGh, identity) {
  if (typeof readGh !== 'function') throw new Error('Public GitHub reader required');
  validateIdentity(identity);
  const expected = continuationApprovalMetadata(identity);
  const issue = readIssue(readGh, identity.issue);
  verifyCurrentIssue(issue, identity.issue);
  const before = issueSnapshot(issue);
  verifyIssueMetadata(issue, expected);

  const firstReview = verifyReviewFromGh(readGh, REPO, identity.issue, issue);
  const commentsBefore = readComments(readGh, issue);
  const continuationBefore = verifyContinuationComment(
    findContinuationComment(commentsBefore, identity.commentId), identity.issue, firstReview.commentId);
  const mainBefore = currentMainSha(readGh);
  if (mainBefore !== identity.sourceSha) throw new Error('Approved source is not current main');

  const currentReview = verifyReviewFromGh(readGh, REPO, identity.issue, issue);
  if (currentReview.commentId !== firstReview.commentId || currentReview.revision !== firstReview.revision) {
    throw new Error('Producer review changed during continuation verification');
  }

  const currentIssue = readIssue(readGh, identity.issue);
  verifyCurrentIssue(currentIssue, identity.issue);
  const after = issueSnapshot(currentIssue);
  const commentsAfter = readComments(readGh, currentIssue);
  const continuationAfter = verifyContinuationComment(
    findContinuationComment(commentsAfter, identity.commentId), identity.issue, currentReview.commentId);
  const mainAfter = currentMainSha(readGh);
  if (before !== after || !sameHistory(commentsBefore, commentsAfter) ||
      commentSnapshot(continuationBefore) !== commentSnapshot(continuationAfter) ||
      mainAfter !== identity.sourceSha || mainAfter !== mainBefore) {
    throw new Error('Continuation authorization changed during verification');
  }

  return {
    approved: true,
    issue: identity.issue,
    commentId: identity.commentId,
    ...expected,
    reviewCommentId: currentReview.commentId,
    revision: currentReview.revision
  };
}

function readPublicMainRef(args, spawn) {
  if (args.length !== 2 || args[0] !== 'api' || args[1] !== MAIN_REF) {
    throw new Error('Unsupported public continuation read');
  }
  const result = spawn('curl', [
    '--disable', '--fail', '--silent', '--show-error', '--max-time', '15', '--proto', '=https',
    '--header', 'Accept: application/vnd.github+json', '--header', 'X-GitHub-Api-Version: 2022-11-28',
    '--header', 'User-Agent: vera-deepseek-continuation-gate', `https://api.github.com/${MAIN_REF}`
  ], {
    encoding: 'utf8', maxBuffer: 1024 * 1024, shell: false,
    env: { PATH: process.env.PATH || '/usr/bin:/bin' }
  });
  if (result.error || result.signal || result.status !== 0) throw new Error('Public main ref read failed');
  return result.stdout;
}

export function readPublicGh(args, spawn = spawnSync) {
  if (args?.at(-1) === MAIN_REF) return readPublicMainRef(args, spawn);
  return readIssueGh(args, spawn);
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
