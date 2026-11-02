// Outbound-only Mac poller. It reads public GitHub metadata, then delegates
// only a manifest-bound request to the existing private controller.
import { createHash, randomUUID } from 'node:crypto';
import { lstatSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { verifyReviewFromGh } from './chat-review-github.mjs';
import { COMMAND, REPO, invokePrivateRunner, requestFromEvent, reserveReceipt, taskCap, verifyCurrentComment, verifyCurrentIssue } from './deepseek-dispatch.mjs';

const API = 'https://api.github.com';
const PAGE_SIZE = 100;
const MAX_PAGES = 10;
const MAX_MANIFEST_BYTES = 64 * 1024;
const SHA256 = /^[a-f0-9]{64}$/;
const GIT_SHA = /^[a-f0-9]{40}$/;

function apiUrl(path) {
  if (!/^\/repos\/mbelinkie\/vera-script-to-timeline\//.test(path)) throw new Error('Unsupported GitHub path');
  return API + path;
}

async function fetchJson(path, fetchImpl = globalThis.fetch) {
  const response = await fetchImpl(apiUrl(path), {
    headers: {
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'vera-deepseek-receiver'
    },
    redirect: 'error',
    signal: globalThis.AbortSignal.timeout(15_000)
  });
  if (!response.ok) throw new Error('Public GitHub read failed: HTTP ' + response.status);
  return response.json();
}

function nextPage(link, page) {
  if (!link) return false;
  const next = link.split(',').find(value => /rel="next"/.test(value));
  if (!next) return false;
  const url = next.match(/<([^>]+)>/);
  if (!url) throw new Error('Unexpected GitHub pagination link');
  const parsed = new globalThis.URL(url[1]);
  if (parsed.origin !== API || parsed.pathname !== '/repos/' + REPO + '/issues/comments' ||
      parsed.searchParams.get('page') !== String(page + 1) || parsed.searchParams.get('per_page') !== String(PAGE_SIZE) ||
      parsed.searchParams.get('sort') !== 'created' || parsed.searchParams.get('direction') !== 'desc') {
    throw new Error('Unexpected GitHub pagination link');
  }
  return true;
}

export async function listRecentComments(fetchImpl = globalThis.fetch, lastSeenId = null) {
  const comments = [];
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const response = await fetchImpl(apiUrl('/repos/' + REPO + '/issues/comments?per_page=' + PAGE_SIZE +
      '&sort=created&direction=desc&page=' + page), {
      headers: { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vera-deepseek-receiver' },
      redirect: 'error',
      signal: globalThis.AbortSignal.timeout(15_000)
    });
    if (!response.ok) throw new Error('Public GitHub comment poll failed: HTTP ' + response.status);
    const pageComments = await response.json();
    if (!Array.isArray(pageComments) || pageComments.length > PAGE_SIZE ||
        !pageComments.every(comment => Number.isSafeInteger(comment?.id) && comment.id > 0 && typeof comment.body === 'string')) {
      throw new Error('GitHub comment page is malformed');
    }
    for (let index = 1; index < pageComments.length; index += 1) {
      if (pageComments[index - 1].id <= pageComments[index].id) throw new Error('GitHub comment order is invalid');
    }
    comments.push(...pageComments);
    if (lastSeenId === null || pageComments.some(comment => comment.id <= lastSeenId) ||
        !nextPage(response.headers.get('link'), page)) return comments;
  }
  throw new Error('GitHub comment pagination exceeded its safe bound');
}

function privateFile(path, { directory = false, readOnly = true } = {}) {
  const st = lstatSync(path);
  const expectedType = directory ? st.isDirectory() : st.isFile();
  const owner = typeof process.getuid === 'function' ? st.uid === process.getuid() : true;
  const privateMode = directory
    ? (st.mode & 0o077) === 0
    : (st.mode & 0o077) === 0 && (readOnly ? (st.mode & 0o222) === 0 : (st.mode & 0o022) === 0) && (st.mode & 0o400) !== 0;
  if (!expectedType || st.isSymbolicLink() || !owner || !privateMode) {
    throw new Error('Private receiver state has unsafe type, owner, or permissions');
  }
  return st;
}

export function readCursor(path) {
  try {
    privateFile(path);
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
  const cursor = JSON.parse(readFileSync(path, 'utf8'));
  if (cursor?.repository !== REPO || !Number.isSafeInteger(cursor.lastCommentId) || cursor.lastCommentId < 0) {
    throw new Error('Receiver cursor is invalid');
  }
  return cursor.lastCommentId;
}

export function writeCursor(path, lastCommentId) {
  if (!Number.isSafeInteger(lastCommentId) || lastCommentId < 0) throw new Error('Receiver cursor is invalid');
  const dir = dirname(path);
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  privateFile(dir, { directory: true });
  const temporary = path + '.' + randomUUID() + '.tmp';
  writeFileSync(temporary, JSON.stringify({ repository: REPO, lastCommentId }) + '\n', { flag: 'wx', mode: 0o400 });
  renameSync(temporary, path);
}

export function validateManifest(manifest, issue, commentId, currentMainSha) {
  const safePath = value => typeof value === 'string' && value.length > 0 && !value.startsWith('/') &&
    !value.startsWith('~') && !value.includes('\\') && value.split('/').every(part => part && part !== '.' && part !== '..') &&
    !value.startsWith('.github/') && !value.split('').some(character => character.charCodeAt(0) < 32);
  const safeCommand = command => Array.isArray(command) && command.length > 0 &&
    ['node', 'npm', 'python', 'python3', 'uv'].includes(command[0]) &&
    command.every(part => typeof part === 'string' && !part.split('').some(character => character.charCodeAt(0) < 32));
  if (!manifest || manifest.schemaVersion !== 1 || manifest.issueNumber !== issue ||
      manifest.dispatchCommentId !== commentId || manifest.approvedBy !== 'mbelinkie' ||
      typeof manifest.approvedAt !== 'string' || !Number.isFinite(Date.parse(manifest.approvedAt)) ||
      new Date(manifest.approvedAt).toISOString() !== manifest.approvedAt ||
      !GIT_SHA.test(manifest.sourceSha) || manifest.sourceSha !== currentMainSha ||
      !Array.isArray(manifest.allowedFiles) || manifest.allowedFiles.length < 1 ||
      !manifest.allowedFiles.every(safePath) || new Set(manifest.allowedFiles).size !== manifest.allowedFiles.length ||
      !Array.isArray(manifest.frozenTests) || manifest.frozenTests.length < 1 ||
      !manifest.frozenTests.every(test => safePath(test?.path) && SHA256.test(test.sha256)) ||
      !Array.isArray(manifest.allowedCommands) || manifest.allowedCommands.length < 1 ||
      !manifest.allowedCommands.every(safeCommand) ||
      !Number.isSafeInteger(manifest.maxRepairAttempts) || manifest.maxRepairAttempts < 1 || manifest.maxRepairAttempts > 3) {
    throw new Error('Approved private task manifest is missing, stale, or outside bounds');
  }
  const cap = taskCap(String(manifest.taskCapUsd));
  return { cap };
}

export function loadApprovedManifest(path, issue, commentId, currentMainSha) {
  privateFile(dirname(path), { directory: true });
  const st = privateFile(path);
  if (st.size > MAX_MANIFEST_BYTES) throw new Error('Private task manifest exceeds its safe bound');
  const raw = readFileSync(path);
  const manifest = JSON.parse(raw.toString('utf8'));
  const validated = validateManifest(manifest, issue, commentId, currentMainSha);
  return { manifest, ...validated, sha256: createHash('sha256').update(raw).digest('hex') };
}

export function readPublicGh(args, spawn = spawnSync) {
  const route = args.at(-1);
  if (args[0] !== 'api' || typeof route !== 'string') throw new Error('Unsupported canonical review read');
  const issue = route.match(/^repos\/mbelinkie\/vera-script-to-timeline\/issues\/(\d+)$/);
  const comments = route.match(/^repos\/mbelinkie\/vera-script-to-timeline\/issues\/(\d+)\/comments\?per_page=100$/);
  if (!issue && !comments) throw new Error('Unsupported canonical review path');
  const base = '/repos/' + REPO + '/issues/' + (issue?.[1] || comments?.[1]);
  const get = path => {
    const result = spawn('curl', ['--disable', '--fail', '--silent', '--show-error', '--max-time', '15',
      '--proto', '=https', '--header', 'Accept: application/vnd.github+json', '--header',
      'X-GitHub-Api-Version: 2022-11-28', '--header', 'User-Agent: vera-deepseek-receiver', apiUrl(path)],
    { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, shell: false, env: { PATH: process.env.PATH || '/usr/bin:/bin' } });
    if (result.error || result.signal || result.status !== 0) throw new Error('Public GitHub review read failed');
    return result.stdout;
  };
  if (issue) return get(base);
  if (!args.includes('--paginate') || !args.includes('--slurp')) throw new Error('Incomplete review history request');
  const countPath = get(base);
  const count = JSON.parse(countPath).comments;
  if (!Number.isSafeInteger(count) || count < 0 || count > 2000) throw new Error('Review history exceeds safe bounds');
  const pages = [];
  const pageCount = Math.max(1, Math.ceil(count / PAGE_SIZE));
  for (let page = 1; page <= pageCount; page += 1) {
    pages.push(JSON.parse(get(base + '/comments?per_page=100&page=' + page)));
  }
  return JSON.stringify(pages);
}

function safeRunner(path) {
  const st = privateFile(path, { readOnly: false });
  if ((st.mode & 0o111) === 0 || (st.mode & 0o022) !== 0 ||
      (typeof process.getuid === 'function' && st.uid !== process.getuid())) {
    throw new Error('Private runner must be owner-owned, executable, and not group/world-writable');
  }
}

export async function processDispatchComment(comment, {
  allowedActors = [], fetchImpl = globalThis.fetch, readGh = readPublicGh,
  manifestDir = join(homedir(), '.codex', 'deepseek-manifests'),
  receiptRoot = join(homedir(), '.codex', 'deepseek-dispatch-receipts'),
  runner = join(homedir(), '.codex', 'bin', 'vera-deepseek-runner'),
  invoke = invokePrivateRunner
} = {}) {
  if (comment?.body !== COMMAND) return { state: 'ignored' };
  const issueMatch = new RegExp('^https://api\\.github\\.com/repos/' + REPO.replaceAll('/', '\\/') + '/issues/(\\d+)$').exec(comment.issue_url || '');
  if (!issueMatch) return { state: 'refused' };
  const issueNumber = Number(issueMatch[1]);
  const issue = await fetchJson('/repos/' + REPO + '/issues/' + issueNumber, fetchImpl);
  const event = {
    repository: { full_name: REPO, owner: { login: 'mbelinkie' } },
    issue: { number: issueNumber, pull_request: issue.pull_request },
    comment: { id: comment.id, body: comment.body, user: comment.user }
  };
  let request;
  try {
    request = requestFromEvent(event, allowedActors);
    verifyCurrentComment(comment, request, comment.user?.login);
    verifyCurrentIssue(issue, issueNumber);
  } catch {
    return { state: 'refused' };
  }
  const currentMain = await fetchJson('/repos/' + REPO + '/commits/main', fetchImpl);
  if (!GIT_SHA.test(currentMain?.sha || '')) throw new Error('Current main revision is unavailable');
  const manifestPath = join(manifestDir, 'issue-' + issueNumber + '.json');
  let loaded;
  try {
    loaded = loadApprovedManifest(manifestPath, issueNumber, comment.id, currentMain.sha);
  } catch {
    return { state: 'refused' };
  }
  try {
    verifyReviewFromGh(readGh, REPO, issueNumber, { title: issue.title, body: issue.body, labels: issue.labels });
  } catch (error) {
    if (/Public GitHub review read failed/.test(error.message)) throw error;
    return { state: 'refused' };
  }
  const confirmed = await fetchJson('/repos/' + REPO + '/issues/' + issueNumber, fetchImpl);
  const labels = value => (value || []).map(label => typeof label === 'string' ? label : label?.name).sort();
  if (confirmed.title !== issue.title || confirmed.body !== issue.body || confirmed.state !== issue.state ||
      JSON.stringify(labels(confirmed.labels)) !== JSON.stringify(labels(issue.labels))) return { state: 'refused' };
  const confirmedComment = await fetchJson('/repos/' + REPO + '/issues/comments/' + comment.id, fetchImpl);
  try {
    verifyCurrentComment(confirmedComment, request, comment.user.login);
  } catch {
    return { state: 'refused' };
  }
  if (confirmedComment.updated_at !== comment.updated_at) return { state: 'refused' };

  try {
    safeRunner(runner);
  } catch {
    return { state: 'refused' };
  }
  let receipt;
  try {
    receipt = reserveReceipt(receiptRoot, issueNumber, comment.id);
  } catch (error) {
    if (error?.code === 'EEXIST') return { state: 'duplicate' };
    throw error;
  }
  const childEnv = {
    HOME: homedir(), PATH: '/usr/bin:/bin', VERA_REPOSITORY: REPO,
    VERA_ISSUE_NUMBER: String(issueNumber), VERA_DISPATCH_COMMENT_ID: String(comment.id),
    VERA_DEEPSEEK_TASK_CAP_USD: String(loaded.cap), VERA_DEEPSEEK_CAMPAIGN_CAP_USD: '10',
    VERA_DEEPSEEK_RECEIPT: receipt, VERA_DEEPSEEK_MANIFEST_SHA256: loaded.sha256
  };
  const result = invoke(runner, [String(issueNumber), String(comment.id)], childEnv);
  const state = result.error || result.status !== 0 ? 'uncertain-or-failed' : 'worker-returned';
  writeFileSync(receipt, JSON.stringify({ issue: issueNumber, commentId: comment.id, state,
    timestamp: new Date().toISOString(), exitCode: result.status ?? null,
    detail: result.error?.code || null }, null, 2) + '\n', { mode: 0o600 });
  return { state };
}

export async function pollOnce({
  fetchImpl = globalThis.fetch,
  cursorPath = join(homedir(), '.codex', 'deepseek-receiver', 'cursor.json'),
  allowedActors = [],
  processComment = comment => processDispatchComment(comment, { allowedActors, fetchImpl }),
  read = readCursor,
  write = writeCursor,
  list = lastSeen => listRecentComments(fetchImpl, lastSeen)
} = {}) {
  const lastSeen = read(cursorPath);
  const comments = await list(lastSeen);
  if (!Array.isArray(comments) || !comments.every(comment => Number.isSafeInteger(comment?.id) && comment.id > 0) ||
      new Set(comments.map(comment => comment.id)).size !== comments.length) {
    throw new Error('GitHub comment history is incomplete');
  }
  if (lastSeen === null) {
    write(cursorPath, Math.max(0, ...comments.map(comment => comment.id)));
    return { initialized: true, processed: 0 };
  }
  const ordered = comments.filter(comment => comment.id > lastSeen).sort((left, right) => left.id - right.id);
  for (const comment of ordered) {
    await processComment(comment);
    write(cursorPath, comment.id);
  }
  return { initialized: false, processed: ordered.length };
}

export async function main(env = process.env) {
  if (env.VERA_DEEPSEEK_DISPATCH_ENABLED !== 'true') {
    console.log('Mac receiver disabled; no GitHub polling or private adapter call.');
    return;
  }
  const allowedActors = (env.VERA_DEEPSEEK_ALLOWED_ACTORS || '').split(',').map(actor => actor.trim()).filter(Boolean);
  const codexDir = join(homedir(), '.codex');
  mkdirSync(codexDir, { recursive: true, mode: 0o700 });
  const lock = join(codexDir, 'deepseek-receiver.lock');
  try {
    mkdirSync(lock, { mode: 0o700 });
  } catch (error) {
    if (error?.code === 'EEXIST') throw new Error('Another Mac receiver poll is active or needs manual recovery', { cause: error });
    throw error;
  }
  let result;
  try {
    result = await pollOnce({ allowedActors });
  } finally {
    rmSync(lock, { recursive: true, force: true });
  }
  console.log('Mac receiver poll complete; comments processed: ' + result.processed + '.');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => {
    console.error('DeepSeek receiver refused: ' + error.message);
    process.exitCode = 1;
  });
}
