// GitHub issue-comment -> preinstalled private DeepSeek repair controller.
// This trusted dispatcher never calls a model or merges a PR.
import { lstatSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { verifyReviewFromGh } from './chat-review-github.mjs';

export const REPO = 'mbelinkie/vera-script-to-timeline';
export const COMMAND = '/deepseek dispatch';
export const APPROVAL_LABELS = ['chat-reviewed', 'deepseek-eligible', 'deepseek-ready', 'deepseek-dispatch'];

export function requestFromEvent(event, allowedActors = []) {
  if (event?.repository?.full_name !== REPO) throw new Error('Wrong repository');
  if (event?.issue?.pull_request) throw new Error('Pull requests cannot be dispatched');
  if (event?.comment?.body !== COMMAND) throw new Error('Not an exact dispatch command');
  const login = event?.comment?.user?.login;
  if (!login || (login !== event?.repository?.owner?.login && !allowedActors.includes(login))) {
    throw new Error('Dispatch actor is not allowlisted');
  }
  if (!Number.isSafeInteger(event?.comment?.id) || event.comment.id < 1 ||
      !Number.isSafeInteger(event?.issue?.number) || event.issue.number < 1) {
    throw new Error('Invalid issue/comment identifier');
  }
  return { issue: event.issue.number, commentId: event.comment.id };
}

export function verifyCurrentComment(comment, request, expectedLogin) {
  const issueUrl = `https://api.github.com/repos/${REPO}/issues/${request.issue}`;
  if (comment?.id !== request.commentId || comment.body !== COMMAND ||
      comment.issue_url !== issueUrl || comment.user?.login !== expectedLogin) {
    throw new Error('Dispatch comment changed or does not match the live issue');
  }
  return true;
}

export function verifyCurrentIssue(issue, expectedIssue) {
  if (issue?.number !== expectedIssue || issue.state !== 'open' || issue.pull_request) {
    throw new Error('Issue no longer open or not an issue');
  }
  const labels = new Set((issue.labels || []).map(x => typeof x === 'string' ? x : x.name));
  for (const label of APPROVAL_LABELS) {
    if (!labels.has(label)) throw new Error('Missing required label: ' + label);
  }
  // Explicit opt-in is insufficient for work classified as design or non-DeepSeek.
  // Fail closed on conflicting classification; a human must re-triage the ticket.
  const prohibited = ['type:design', 'type:ux', 'type:research', 'type:product',
    'execution:codex', 'execution:design', 'execution:human', 'deepseek-excluded'];
  for (const label of prohibited) {
    if (labels.has(label)) throw new Error('DeepSeek excluded by classification: ' + label);
  }
  if (labels.has('owner:claude') || labels.has('owner:codex')) {
    throw new Error('Issue is assigned to another execution owner');
  }
  const types = [...labels].filter(label => label.startsWith('type:'));
  if (types.length !== 1 || !['type:implementation', 'type:bug'].includes(types[0])) {
    throw new Error('Only specifically classified implementation or bug issues may use DeepSeek');
  }
  if (labels.has('chat-review-pending')) throw new Error('Chat review still pending');
  if (labels.has('needs:model-escalation')) throw new Error('Model escalation still required');
  // A heading alone is not an approved task. The private adapter must still
  // verify the full owner-approved frozen manifest before doing any work.
  const lines = (issue.body || '').split(/\r?\n/);
  const start = lines.findIndex(line => /^## DeepSeek Handoff[ \t]*$/.test(line));
  if (start < 0) throw new Error('Missing approved DeepSeek Handoff section');
  const next = lines.findIndex((line, index) => index > start && /^#{1,2} /.test(line));
  const handoff = lines.slice(start + 1, next < 0 ? undefined : next)
    .join('\n').replace(/<!--[\s\S]*?-->/g, '').trim();
  if (!/[A-Za-z0-9]/.test(handoff)) throw new Error('Empty DeepSeek Handoff section');
  return true;
}

function labelNames(issue) {
  return (issue?.labels || []).map(label => typeof label === 'string' ? label : label?.name).sort();
}

export function verifyFreshDispatch({
  issue, comment, currentMainSha, request, actor, expectedIssue, expectedComment, expectedMainSha
}) {
  verifyCurrentIssue(issue, request.issue);
  verifyCurrentComment(comment, request, actor);
  if (currentMainSha !== expectedMainSha || comment.updated_at !== expectedComment.updated_at ||
      issue.title !== expectedIssue.title || issue.body !== expectedIssue.body || issue.state !== expectedIssue.state ||
      issue.updated_at !== expectedIssue.updated_at || issue.comments !== expectedIssue.comments ||
      JSON.stringify(labelNames(issue)) !== JSON.stringify(labelNames(expectedIssue))) {
    throw new Error('Dispatch authorization changed before the private runner call');
  }
  return true;
}

export function taskCap(value) {
  // This is an additional per-task ceiling, NOT a replacement for the
  // private controller's required cumulative USD10 campaign ledger.
  if (!value || !/^\d+(?:\.\d{1,4})?$/.test(value)) {
    throw new Error('Set VERA_DEEPSEEK_TASK_CAP_USD to a positive number');
  }
  const cap = Number(value);
  if (!(cap > 0 && cap <= 0.25)) throw new Error('Task cap must be >0 and <=0.25 USD');
  return cap;
}

export function reserveReceipt(root, issue, commentId) {
  // mkdir is atomic on one host. Never clear this guard automatically:
  // an interrupted/uncertain paid call requires manual ledger reconciliation.
  const dir = join(root, 'issue-' + issue);
  const assertPrivateDirectory = path => {
    const st = lstatSync(path);
    if (!st.isDirectory() || st.isSymbolicLink() ||
        (typeof process.getuid === 'function' && st.uid !== process.getuid()) || (st.mode & 0o077) !== 0) {
      throw new Error('Private receipt state has unsafe type, owner, or permissions');
    }
  };
  mkdirSync(dirname(root), { recursive: true, mode: 0o700 });
  assertPrivateDirectory(dirname(root));
  try {
    mkdirSync(root, { mode: 0o700 });
  } catch (error) {
    if (error?.code !== 'EEXIST') throw error;
  }
  assertPrivateDirectory(root);
  try {
    mkdirSync(dir, { mode: 0o700 });
  } catch (error) {
    if (error?.code !== 'EEXIST') throw error;
    assertPrivateDirectory(dir);
    throw error;
  }
  assertPrivateDirectory(dir);
  const receipt = join(dir, 'receipt.json');
  writeFileSync(receipt, JSON.stringify({
    issue, commentId, state: 'reserved',
    timestamp: new Date().toISOString()
  }, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
  return receipt;
}

export function writeReceipt(path, value) {
  const dir = dirname(path);
  const st = lstatSync(dir);
  if (!st.isDirectory() || st.isSymbolicLink() ||
      (typeof process.getuid === 'function' && st.uid !== process.getuid()) || (st.mode & 0o077) !== 0) {
    throw new Error('Private receipt state has unsafe type, owner, or permissions');
  }
  const temporary = path + '.' + randomUUID() + '.tmp';
  try {
    writeFileSync(temporary, JSON.stringify(value, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    renameSync(temporary, path);
  } catch (error) {
    rmSync(temporary, { force: true });
    throw error;
  }
}

export function invokePrivateRunner(runner, args, env, spawn = spawnSync) {
  return spawn(runner, args, {
    env, shell: false, stdio: 'ignore', timeout: 40 * 60 * 1000
  });
}

async function fetchGitHubJson(token, url) {
  const response = await globalThis.fetch(url, {
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'vera-deepseek-dispatch'
    }
  });
  if (!response.ok) throw new Error('GitHub request validation failed: HTTP ' + response.status);
  return response.json();
}

function readGhForReview(token, args) {
  const result = spawnSync('gh', args, {
    encoding: 'utf8',
    maxBuffer: 16 * 1024 * 1024,
    env: { ...process.env, GH_TOKEN: token, GITHUB_TOKEN: token }
  });
  if (result.error || result.signal || result.status !== 0) {
    throw new Error('Canonical Producer review check failed');
  }
  return result.stdout;
}

export async function validateLiveRequest(event, {
  allowedActors = [],
  token,
  taskCapUsd = '0.25',
  fetchJson = url => fetchGitHubJson(token, url),
  readGh = args => readGhForReview(token, args),
} = {}) {
  const request = requestFromEvent(event, allowedActors);
  if (typeof token !== 'string' || !token) throw new Error('Missing GitHub issue-read token');
  const actor = event.comment.user.login;
  const liveComment = await fetchJson(`https://api.github.com/repos/${REPO}/issues/comments/${request.commentId}`);
  verifyCurrentComment(liveComment, request, actor);
  const issue = await fetchJson(`https://api.github.com/repos/${REPO}/issues/${request.issue}`);
  verifyCurrentIssue(issue, request.issue);
  taskCap(taskCapUsd);
  const review = verifyReviewFromGh(
    readGh,
    REPO,
    request.issue,
    { title: issue.title, body: issue.body, labels: issue.labels },
  );
  verifyCurrentComment(await fetchJson(`https://api.github.com/repos/${REPO}/issues/comments/${request.commentId}`), request, actor);
  return { request, reviewCommentId: review.commentId };
}

export async function main(env = process.env) {
  const event = JSON.parse(readFileSync(env.GITHUB_EVENT_PATH, 'utf8'));
  const allowedActors = (env.VERA_DEEPSEEK_ALLOWED_ACTORS || '').split(',')
    .map(actor => actor.trim()).filter(Boolean);
  requestFromEvent(event, allowedActors);
  if (!env.GITHUB_TOKEN) throw new Error('Missing GitHub issue-read token');
  const { reviewCommentId } = await validateLiveRequest(event, {
    allowedActors,
    token: env.GITHUB_TOKEN,
    taskCapUsd: env.VERA_DEEPSEEK_TASK_CAP_USD,
    fetchJson: url => fetchGitHubJson(env.GITHUB_TOKEN, url),
    readGh: args => readGhForReview(env.GITHUB_TOKEN, args),
  });
  if (env.VERA_DEEPSEEK_DISPATCH_ENABLED !== 'true') {
    console.log('GitHub request validated against current issue review (comment ' + reviewCommentId +
      '); dispatch is globally disabled and nothing was forwarded.');
    return;
  }
  console.log('GitHub request validated against current issue review (comment ' + reviewCommentId +
    '); the hosted job never invokes the private adapter or creates a receipt.');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => {
    console.error('DeepSeek dispatch refused: ' + error.message);
    process.exitCode = 1;
  });
}
