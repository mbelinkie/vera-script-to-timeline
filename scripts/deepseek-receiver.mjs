// Outbound-only Mac poller. It reads public GitHub metadata, then delegates
// only a manifest-bound request to the existing private controller.
import { createHash, randomUUID } from 'node:crypto';
import { lstatSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { basename, dirname, isAbsolute, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { hostPreflight } from './deepseek-host-preflight.mjs';
import { liveApprovalMetadata, verifyLiveApproval, readPublicGh as readLiveGh } from './deepseek-live-gate.mjs';
import { verifyReviewFromGh } from './chat-review-github.mjs';
import { COMMAND, REPO, RESEARCH_REPO, invokePrivateRunner, requestFromEvent, requireDispatchRepo, reserveReceipt, taskCap, verifyCurrentComment, verifyCurrentIssue, verifyFreshDispatch, writeReceipt } from './deepseek-dispatch.mjs';

const API = 'https://api.github.com';
const PAGE_SIZE = 100;
const MAX_MANIFEST_BYTES = 64 * 1024;
const SHA256 = /^[a-f0-9]{64}$/;
const GIT_SHA = /^[a-f0-9]{40}$/;

const TASK_ROOT = join(homedir(), '.local', 'share', 'vera', 'deepseek', 'tasks');
const RECEIPT_ROOT = join(homedir(), '.codex', 'deepseek-dispatch-receipts');
const CURSOR_PATH = join(homedir(), '.codex', 'deepseek-receiver', 'cursor.json');

function repositoryStateDir(root, repository) {
  const slug = requireDispatchRepo(repository);
  return repository === REPO ? root : join(root, slug);
}

function repositoryCursorPath(path, repository) {
  const slug = requireDispatchRepo(repository);
  return repository === REPO ? path : join(dirname(path), slug, basename(path));
}

function apiUrl(path, repository = REPO) {
  requireDispatchRepo(repository);
  if (!path.startsWith('/repos/mbelinkie/' + requireDispatchRepo(repository) + '/')) {
    throw new Error('Unsupported GitHub path');
  }
  return API + path;
}

async function fetchJson(path, fetchImpl = globalThis.fetch, repository = REPO) {
  const response = await fetchImpl(apiUrl(path, repository), {
    headers: {
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      'User-Agent': 'vera-deepseek-receiver'
    },
    redirect: 'error',
    signal: globalThis.AbortSignal.timeout(15_000)
  });
  if (!response.ok) {
    const error = new Error('Public GitHub read failed: HTTP ' + response.status);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function isRetryableHttpError(error) {
  return [401, 403, 408, 429].includes(error?.status) || error?.status >= 500;
}

function isTerminalHttpError(error) {
  return Number.isInteger(error?.status) && error.status >= 400 && error.status < 500 && !isRetryableHttpError(error);
}

export async function listRecentComments(fetchImpl = globalThis.fetch, lastSeenId = null, lastSeenCreatedAt = null,
  { repository = REPO } = {}) {
  const slug = requireDispatchRepo(repository);
  let direction = 'desc';
  let since = null;
  if (lastSeenId !== null) {
    const timestamp = Date.parse(lastSeenCreatedAt || '');
    if (!Number.isFinite(timestamp)) throw new Error('Receiver cursor timestamp is missing or invalid');
    since = new Date(Math.max(0, timestamp - 1000)).toISOString();
    direction = 'asc';
  }
  const comments = [];
  const query = new globalThis.URLSearchParams({ per_page: String(PAGE_SIZE), sort: 'created', direction, page: '1' });
  if (since !== null) query.set('since', since);
  const response = await fetchImpl(apiUrl('/repos/mbelinkie/' + slug + '/issues/comments?' + query, repository), {
    headers: { Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'vera-deepseek-receiver' },
    redirect: 'error',
    signal: globalThis.AbortSignal.timeout(15_000)
  });
  if (!response.ok) {
    const error = new Error('Public GitHub comment poll failed: HTTP ' + response.status);
    error.status = response.status;
    throw error;
  }
  const pageComments = await response.json();
  if (!Array.isArray(pageComments) || pageComments.length > PAGE_SIZE ||
      !pageComments.every(comment => Number.isSafeInteger(comment?.id) && comment.id > 0 && typeof comment.body === 'string' &&
        (lastSeenId === null || typeof comment.created_at === 'string' && Number.isFinite(Date.parse(comment.created_at))))) {
    throw new Error('GitHub comment page is malformed');
  }
  for (let index = 1; index < pageComments.length; index += 1) {
    const ordered = direction === 'desc'
      ? pageComments[index - 1].id > pageComments[index].id
      : pageComments[index - 1].id < pageComments[index].id;
    if (!ordered) throw new Error('GitHub comment order is invalid');
  }
  comments.push(...pageComments);
  return comments;
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

export function readCursor(path, { repository = REPO } = {}) {
  return readCursorRecord(path, repository)?.lastCommentId ?? null;
}

function readCursorCreatedAt(path, { repository = REPO } = {}) {
  return readCursorRecord(path, repository)?.lastCommentCreatedAt ?? null;
}

function readCursorRecord(path, repository = REPO) {
  requireDispatchRepo(repository);
  try {
    privateFile(path);
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
  const cursor = JSON.parse(readFileSync(path, 'utf8'));
  if (cursor?.repository !== repository || !Number.isSafeInteger(cursor.lastCommentId) || cursor.lastCommentId < 0) {
    throw new Error('Receiver cursor is invalid');
  }
  if (cursor.lastCommentCreatedAt !== undefined &&
      (typeof cursor.lastCommentCreatedAt !== 'string' || !Number.isFinite(Date.parse(cursor.lastCommentCreatedAt)))) {
    throw new Error('Receiver cursor timestamp is invalid');
  }
  return cursor;
}

export function writeCursor(path, lastCommentId, lastCommentCreatedAt = null, { repository = REPO } = {}) {
  requireDispatchRepo(repository);
  if (!Number.isSafeInteger(lastCommentId) || lastCommentId < 0) throw new Error('Receiver cursor is invalid');
  if (lastCommentCreatedAt !== null &&
      (typeof lastCommentCreatedAt !== 'string' || !Number.isFinite(Date.parse(lastCommentCreatedAt)))) {
    throw new Error('Receiver cursor timestamp is invalid');
  }
  const dir = dirname(path);
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  privateFile(dir, { directory: true });
  const temporary = path + '.' + randomUUID() + '.tmp';
  const cursor = { repository, lastCommentId };
  if (lastCommentCreatedAt !== null) cursor.lastCommentCreatedAt = lastCommentCreatedAt;
  writeFileSync(temporary, JSON.stringify(cursor) + '\n', { flag: 'wx', mode: 0o400 });
  renameSync(temporary, path);
}

export function liveIdentity(manifest, manifestSha, { repository = REPO } = {}) {
  requireDispatchRepo(repository);
  return {
    ...(repository === REPO ? {} : { repository }),
    issue: manifest.issue, commentId: manifest.dispatch_comment_id, manifestSha,
    sourceSha: manifest.base_sha, adapterSha: manifest.adapter_sha256,
    reconciliationSha: manifest.reconciliation_sha256, attemptId: manifest.attempt_id,
    campaign: manifest.campaign, model: manifest.model, maxOutputTokens: manifest.max_output_tokens
  };
}

export function validateManifest(manifest, issue, commentId, currentMainSha, { repository = REPO } = {}) {
  requireDispatchRepo(repository);
  const safePath = value => typeof value === 'string' && value.length > 0 && !value.startsWith('/') &&
    !value.startsWith('~') && !value.includes('\\') && value.split('/').every(part => part && part !== '.' && part !== '..') &&
    !value.startsWith('.github/') && !value.split('').some(character => character.charCodeAt(0) < 32);
  const safeGatePath = value => typeof value === 'string' && value.length > 0 && !value.startsWith('/') &&
    !value.startsWith('~') && !value.includes('\\') && value.split('/').every(part => part && part !== '.' && part !== '..') &&
    !value.split('').some(character => character.charCodeAt(0) < 32);
  const safeCommand = command => Array.isArray(command) && command.length >= 2 && command.length <= 12 &&
    typeof command[0] === 'string' && isAbsolute(command[0]) && command.every(part =>
      typeof part === 'string' && part.length > 0 && part.length < 300 && part !== '-c' && part !== '-e' &&
      !part.includes('/bin/sh') && !part.split('').some(character => character.charCodeAt(0) < 32));
  const frozen = manifest?.frozen_files;
  const scope = manifest?.edit_scope;
  const validScope = scope?.mode === 'full_file' ? scope.approve_entire_file === true :
    scope?.mode === 'bounded_region' && ['start_marker', 'end_marker'].every(key =>
      typeof scope[key] === 'string' && scope[key].length >= 8 && scope[key].length <= 300);
  const legacyMock = repository === REPO && manifest?.schema === 1 && manifest.transport_contract === 'VERA_DEEPSEEK_RECEIVER_V1' &&
    (manifest.execution_mode === undefined || manifest.execution_mode === 'mock');
  const versioned = manifest?.schema === 2 && manifest.transport_contract === 'VERA_DEEPSEEK_RECEIVER_V2' &&
    ['mock', 'live'].includes(manifest.execution_mode);
  const mode = versioned ? manifest.execution_mode : 'mock';
  if (!manifest || !(legacyMock || versioned) || manifest.issue !== issue || manifest.repository !== repository ||
      manifest.dispatch_comment_id !== commentId ||
      manifest.operator_approved !== true || manifest.public_synthetic_only !== true ||
      !GIT_SHA.test(manifest.base_sha) || manifest.base_sha !== currentMainSha ||
      !SHA256.test(manifest.adapter_sha256) || !safePath(manifest.editable_file) || !SHA256.test(manifest.editable_sha256) ||
      !frozen || typeof frozen !== 'object' || Array.isArray(frozen) || Object.keys(frozen).length < 1 ||
      Object.keys(frozen).length > 25 || Object.hasOwn(frozen, manifest.editable_file) ||
      !Object.entries(frozen).every(([path, digest]) => safePath(path) && SHA256.test(digest)) || !validScope ||
      !Array.isArray(manifest.checks) || manifest.checks.length < 1 || manifest.checks.length > 3 ||
      !manifest.checks.every(safeCommand) || typeof manifest.source_repo !== 'string' || !isAbsolute(manifest.source_repo) ||
      !Number.isSafeInteger(manifest.max_rounds) || manifest.max_rounds < 1 || manifest.max_rounds > 3 ||
      !Number.isSafeInteger(manifest.max_output_tokens) || manifest.max_output_tokens < 512 || manifest.max_output_tokens > 24000 ||
      typeof manifest.task_instructions !== 'string' || manifest.task_instructions.length < 40 || manifest.task_instructions.length > 6000 ||
      manifest.live_enabled !== (mode === 'live') ||
      (mode === 'mock' && (typeof manifest.mock_replacement !== 'string' ||
       manifest.mock_replacement.length < 1 || manifest.mock_replacement.length > 90000))) {
    throw new Error('Approved private task manifest is missing, stale, or outside bounds');
  }
  const cap = taskCap(String(manifest.task_cap_usd));
  if (mode === 'live') {
    const metadata = liveApprovalMetadata(liveIdentity(manifest, '0'.repeat(64), { repository }));
    const liveGateFiles = manifest.live_gate_files;
    const validResearchLiveGate = repository !== RESEARCH_REPO ||
      typeof manifest.live_gate_repo === 'string' && isAbsolute(manifest.live_gate_repo) &&
      GIT_SHA.test(manifest.live_gate_base_sha || '') && liveGateFiles && typeof liveGateFiles === 'object' &&
      !Array.isArray(liveGateFiles) && Object.keys(liveGateFiles).length > 0 && Object.keys(liveGateFiles).length <= 25 &&
      Object.entries(liveGateFiles).every(([path, digest]) => safeGatePath(path) && SHA256.test(digest));
    const age = Date.now() - Date.parse(manifest.pricing_verified_on + 'T00:00:00.000Z');
    if (manifest.live_contract !== 'VERA_DEEPSEEK_LIVE_V2' || Object.hasOwn(manifest, 'mock_replacement') ||
        Object.hasOwn(manifest, 'continuation_contract') ||
        manifest.max_rounds !== 1 || String(manifest.task_cap_usd) !== '0.25' ||
        manifest.campaign_cap_usd !== '0.25' || manifest.lifetime_cap_usd !== '10' ||
        manifest.max_input_units !== 20000 || manifest.reasoning_effort !== 'high' ||
        !validResearchLiveGate ||
        !SHA256.test(manifest.ledger_sha256 || '') ||
        !/^\d{4}-\d{2}-\d{2}$/.test(manifest.pricing_verified_on || '') ||
        !Number.isFinite(age) || age < 0 || age >= 8 * 86400000 ||
        JSON.stringify(manifest.verified_rates) !== JSON.stringify(metadata.verifiedRates)) {
      throw new Error('Live task requires exact approved single-attempt pricing and accounting bounds');
    }
  }
  return { cap, mode };
}

export function loadApprovedManifest(path, issue, commentId, currentMainSha, { repository = REPO } = {}) {
  privateFile(dirname(path), { directory: true });
  const st = privateFile(path);
  if (st.size > MAX_MANIFEST_BYTES) throw new Error('Private task manifest exceeds its safe bound');
  const raw = readFileSync(path);
  const manifest = JSON.parse(raw.toString('utf8'));
  const validated = validateManifest(manifest, issue, commentId, currentMainSha, { repository });
  return { manifest, ...validated, sha256: createHash('sha256').update(raw).digest('hex') };
}

export function readPublicGh(args, spawn = spawnSync, { repository: expectedRepository } = {}) {
  const route = args.at(-1);
  if (args[0] !== 'api' || typeof route !== 'string') throw new Error('Unsupported canonical review read');
  const match = /^repos\/(mbelinkie\/(?:vera-script-to-timeline|vera-research-video-clips))\/(.+)$/.exec(route);
  if (!match) throw new Error('Unsupported canonical review path');
  const repository = match[1];
  requireDispatchRepo(repository);
  if (expectedRepository !== undefined && expectedRepository !== repository) {
    throw new Error('Canonical review read selected a different repository');
  }
  const issue = match[2].match(/^issues\/(\d+)$/);
  const comments = match[2].match(/^issues\/(\d+)\/comments\?per_page=100$/);
  const main = match[2] === 'git/ref/heads/main';
  if (!issue && !comments && !main) throw new Error('Unsupported canonical review path');
  if (main) {
    const result = spawn('curl', ['--disable', '--fail', '--silent', '--show-error', '--max-time', '15',
      '--proto', '=https', '--header', 'Accept: application/vnd.github+json', '--header',
      'X-GitHub-Api-Version: 2022-11-28', '--header', 'User-Agent: vera-deepseek-receiver',
      apiUrl('/repos/' + repository + '/git/ref/heads/main', repository)],
    { encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, shell: false, env: { PATH: process.env.PATH || '/usr/bin:/bin' } });
    if (result.error || result.signal || result.status !== 0) throw new Error('Public main ref read failed');
    return result.stdout;
  }
  const base = '/repos/' + repository + '/issues/' + (issue?.[1] || comments?.[1]);
  const get = path => {
    const result = spawn('curl', ['--disable', '--fail', '--silent', '--show-error', '--max-time', '15',
      '--proto', '=https', '--header', 'Accept: application/vnd.github+json', '--header',
      'X-GitHub-Api-Version: 2022-11-28', '--header', 'User-Agent: vera-deepseek-receiver', apiUrl(path, repository)],
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

function safeRunner(path, expectedSha256) {
  const st = privateFile(path, { readOnly: false });
  if ((st.mode & 0o111) === 0 || (st.mode & 0o022) !== 0 ||
      (typeof process.getuid === 'function' && st.uid !== process.getuid())) {
    throw new Error('Private runner must be owner-owned, executable, and not group/world-writable');
  }
  if (createHash('sha256').update(readFileSync(path)).digest('hex') !== expectedSha256) {
    throw new Error('Private runner differs from the approved adapter build');
  }
}

export async function processDispatchComment(comment, {
  repository = REPO,
  allowedActors = [], fetchImpl = globalThis.fetch, readGh = readPublicGh,
  manifestDir = TASK_ROOT,
  receiptRoot = RECEIPT_ROOT,
  cursorPath = CURSOR_PATH,
  runner = join(homedir(), '.codex', 'bin', 'vera-deepseek-runner'),
  invoke = invokePrivateRunner, preflight = hostPreflight,
  liveEnabled = false, liveTarget = null, readLive = readLiveGh
} = {}) {
  requireDispatchRepo(repository);
  manifestDir = repositoryStateDir(manifestDir, repository);
  receiptRoot = repositoryStateDir(receiptRoot, repository);
  cursorPath = repositoryCursorPath(cursorPath, repository);
  if (comment?.body !== COMMAND) return { state: 'ignored' };
  const issueMatch = new RegExp('^https://api\\.github\\.com/repos/' + repository.replaceAll('/', '\\/') + '/issues/(\\d+)$').exec(comment.issue_url || '');
  if (!issueMatch) return { state: 'refused' };
  const issueNumber = Number(issueMatch[1]);
  let issue;
  try {
    issue = await fetchJson('/repos/' + repository + '/issues/' + issueNumber, fetchImpl, repository);
  } catch (error) {
    if (isTerminalHttpError(error)) return { state: 'refused' };
    throw error;
  }
  const event = {
    repository: { full_name: repository, owner: { login: 'mbelinkie' } },
    issue: { number: issueNumber, pull_request: issue.pull_request },
    comment: { id: comment.id, body: comment.body, user: comment.user }
  };
  let request;
  try {
    request = requestFromEvent(event, allowedActors);
    verifyCurrentComment(comment, request, comment.user?.login);
    verifyCurrentIssue(issue, issueNumber, {
      repository,
      requireRepositoryUrl: repository === RESEARCH_REPO
    });
  } catch {
    return { state: 'refused' };
  }
  const currentMain = await fetchJson('/repos/' + repository + '/commits/main', fetchImpl, repository);
  if (!GIT_SHA.test(currentMain?.sha || '')) throw new Error('Current main revision is unavailable');
  const manifestPath = join(manifestDir, 'issue-' + issueNumber + '.json');
  let loaded;
  try {
    loaded = loadApprovedManifest(manifestPath, issueNumber, comment.id, currentMain.sha, { repository });
  } catch {
    return { state: 'refused' };
  }
  if (loaded.mode === 'live' && (!liveEnabled ||
      liveTarget?.issue !== issueNumber || liveTarget?.commentId !== comment.id ||
      repository === RESEARCH_REPO && liveTarget?.repository !== repository)) {
    throw new Error('Live event deferred; select its exact approved issue/comment for an enabled one-shot');
  }
  try {
    const selectedReadGh = args => readGh(args, undefined, { repository });
    verifyReviewFromGh(selectedReadGh, repository, issueNumber,
      { title: issue.title, body: issue.body, labels: issue.labels });
  } catch (error) {
    if (/Public GitHub review read failed/.test(error.message)) throw error;
    return { state: 'refused' };
  }
  let confirmed;
  try {
    confirmed = await fetchJson('/repos/' + repository + '/issues/' + issueNumber, fetchImpl, repository);
  } catch (error) {
    if (isTerminalHttpError(error)) return { state: 'refused' };
    throw error;
  }
  const labels = value => (value || []).map(label => typeof label === 'string' ? label : label?.name).sort();
  if (confirmed.title !== issue.title || confirmed.body !== issue.body || confirmed.state !== issue.state ||
      confirmed.repository_url !== issue.repository_url ||
      JSON.stringify(labels(confirmed.labels)) !== JSON.stringify(labels(issue.labels))) return { state: 'refused' };
  let confirmedComment;
  try {
    confirmedComment = await fetchJson('/repos/' + repository + '/issues/comments/' + comment.id, fetchImpl, repository);
  } catch (error) {
    if (isTerminalHttpError(error)) return { state: 'refused' };
    throw error;
  }
  try {
    verifyCurrentComment(confirmedComment, request, comment.user.login);
  } catch {
    return { state: 'refused' };
  }
  if (confirmedComment.updated_at !== comment.updated_at) return { state: 'refused' };

  try {
    safeRunner(runner, loaded.manifest.adapter_sha256);
  } catch {
    return { state: 'refused' };
  }
  try {
    const selectedReadGh = args => readGh(args, undefined, { repository });
    verifyReviewFromGh(selectedReadGh, repository, issueNumber, {
      title: issue.title, body: issue.body, labels: issue.labels
    });
  } catch (error) {
    if (/Public GitHub review read failed/.test(error.message)) throw error;
    return { state: 'refused' };
  }
  let finalIssue;
  let finalComment;
  let finalMain;
  try {
    [finalIssue, finalComment, finalMain] = await Promise.all([
      fetchJson('/repos/' + repository + '/issues/' + issueNumber, fetchImpl, repository),
      fetchJson('/repos/' + repository + '/issues/comments/' + comment.id, fetchImpl, repository),
      fetchJson('/repos/' + repository + '/commits/main', fetchImpl, repository)
    ]);
  } catch (error) {
    if (isTerminalHttpError(error)) return { state: 'refused' };
    throw error;
  }
  // A read-only host refusal must preserve the event for explicit repair/rerun.
  // Legacy mock adapters retain their original no-preflight compatibility.
  if (loaded.mode === 'live') {
    preflight({ runner, adapterSha256: loaded.manifest.adapter_sha256, receiptRoot, cursorPath,
      ...(repository === REPO ? {} : { repository }), allowEnabled: true });
  }
  try {
    verifyFreshDispatch({
      issue: finalIssue, comment: finalComment, currentMainSha: finalMain?.sha, request,
      actor: comment.user.login, expectedIssue: issue, expectedComment: confirmedComment,
      expectedMainSha: currentMain.sha
    });
    const finalManifest = loadApprovedManifest(manifestPath, issueNumber, comment.id, finalMain.sha, { repository });
    if (finalManifest.sha256 !== loaded.sha256) throw new Error('Private task manifest changed');
    safeRunner(runner, finalManifest.manifest.adapter_sha256);
    if (loaded.mode === 'live') verifyLiveApproval(readLive,
      liveIdentity(finalManifest.manifest, finalManifest.sha256, { repository }));
    // Public reads may take time; repeat local manifest/build checks after them.
    const beforeInvoke = loadApprovedManifest(manifestPath, issueNumber, comment.id, finalMain.sha, { repository });
    if (beforeInvoke.sha256 !== loaded.sha256) throw new Error('Private task manifest changed');
    safeRunner(runner, beforeInvoke.manifest.adapter_sha256);
  } catch (error) {
    if (/Public (?:GitHub review|main ref) read failed/.test(error.message)) throw error;
    return { state: 'refused' };
  }
  if (loaded.mode === 'live') {
    try {
      lstatSync(join(receiptRoot, 'issue-' + issueNumber));
      return { state: 'duplicate' };
    } catch (error) {
      if (error?.code !== 'ENOENT') throw error;
    }
  }
  let receipt;
  try {
    // Live uses the existing controller's final-gate receipt allocation. Never
    // overwrite its diagnostic/accounting receipt with a transport-only result.
    receipt = loaded.mode === 'live' ? join(receiptRoot, 'issue-' + issueNumber, 'receipt.json')
      : reserveReceipt(receiptRoot, issueNumber, comment.id, { repository });
  } catch (error) {
    if (error?.code === 'EEXIST') return { state: 'duplicate' };
    throw error;
  }
  const childEnv = {
    HOME: homedir(), PATH: '/usr/bin:/bin', VERA_REPOSITORY: repository,
    VERA_ISSUE_NUMBER: String(issueNumber), VERA_DISPATCH_COMMENT_ID: String(comment.id),
    VERA_DEEPSEEK_TASK_CAP_USD: String(loaded.cap), VERA_DEEPSEEK_CAMPAIGN_CAP_USD: '10',
    VERA_DEEPSEEK_RECEIPT: receipt, VERA_DEEPSEEK_MANIFEST_SHA256: loaded.sha256,
    VERA_DEEPSEEK_SOURCE_SHA: loaded.manifest.base_sha, VERA_DEEPSEEK_EXECUTION_MODE: loaded.mode,
    VERA_DEEPSEEK_ADAPTER_SHA256: loaded.manifest.adapter_sha256,
    ...(loaded.mode === 'live' ? { VERA_DEEPSEEK_LIVE_ENABLED: 'true' } : {})
  };
  const result = invoke(runner, [String(issueNumber), String(comment.id)], childEnv);
  const state = result.error || result.status !== 0 ? 'uncertain-or-failed' : 'worker-returned';
  if (loaded.mode === 'mock') writeReceipt(receipt, { ...(repository === REPO ? {} : { repository }), issue: issueNumber, commentId: comment.id, state,
    timestamp: new Date().toISOString(), exitCode: result.status ?? null,
    detail: result.error?.code || null });
  return { state };
}

export async function pollOnce(options = {}) {
  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  const repository = options.repository ?? REPO;
  requireDispatchRepo(repository);
  const cursorPath = repositoryCursorPath(options.cursorPath ?? CURSOR_PATH, repository);
  const allowedActors = options.allowedActors ?? [];
  const liveEnabled = options.liveEnabled ?? false;
  const liveTarget = options.liveTarget ?? null;
  const read = options.read ?? readCursor;
  const readCreatedAt = options.readCreatedAt ?? readCursorCreatedAt;
  const write = options.write ?? writeCursor;
  const list = options.list;
  const processComment = options.processComment ?? (comment => processDispatchComment(comment, {
    repository, allowedActors, fetchImpl, cursorPath: options.cursorPath ?? CURSOR_PATH, liveEnabled, liveTarget
  }));
  const lastSeen = read(cursorPath, { repository });
  let lastSeenCreatedAt = readCreatedAt(cursorPath, { repository });
  const useDefaultList = list === undefined;
  if (lastSeen !== null && lastSeenCreatedAt === null) {
    if (lastSeen === 0) {
      lastSeenCreatedAt = '1970-01-01T00:00:00.000Z';
    } else if (useDefaultList) {
      try {
        const anchor = await fetchJson('/repos/' + repository + '/issues/comments/' + lastSeen, fetchImpl, repository);
        if (anchor?.id !== lastSeen || typeof anchor.created_at !== 'string' || !Number.isFinite(Date.parse(anchor.created_at))) {
          throw new Error('Receiver cursor anchor is invalid');
        }
        lastSeenCreatedAt = anchor.created_at;
        write(cursorPath, lastSeen, lastSeenCreatedAt, { repository });
      } catch (error) {
        if (error?.status === 404 || error?.status === 410) {
          throw new Error('Receiver cursor anchor was deleted; manual cursor recovery is required', { cause: error });
        }
        throw error;
      }
    }
  }
  const listComments = list || ((lastSeenId, createdAt) =>
    listRecentComments(fetchImpl, lastSeenId, createdAt, { repository }));
  const comments = await listComments(lastSeen, lastSeenCreatedAt, { repository });
  if (!Array.isArray(comments) || !comments.every(comment => Number.isSafeInteger(comment?.id) && comment.id > 0) ||
      new Set(comments.map(comment => comment.id)).size !== comments.length) {
    throw new Error('GitHub comment history is incomplete');
  }
  if (lastSeen === null) {
    const latest = comments.reduce((current, comment) => !current || comment.id > current.id ? comment : current, null);
    write(cursorPath, latest?.id ?? 0, latest?.created_at ?? (latest ? null : '1970-01-01T00:00:00.000Z'), { repository });
    return { initialized: true, processed: 0 };
  }
  const ordered = comments.filter(comment => comment.id > lastSeen).sort((left, right) => left.id - right.id);
  for (const comment of ordered) {
    await processComment(comment);
    write(cursorPath, comment.id, comment.created_at ?? null, { repository });
  }
  return { initialized: false, processed: ordered.length };
}

export function parseReceiverArgs(argv = []) {
  if (!Array.isArray(argv) || !argv.every(value => typeof value === 'string')) {
    throw new Error('Receiver arguments must be strings');
  }
  if (argv[0] === '--preflight') {
    if (argv.length === 2) return { preflight: true, repository: REPO, adapterSha256: argv[1] };
    if (argv.length === 4 && argv[1] === '--repo') {
      requireDispatchRepo(argv[2]);
      return { preflight: true, repository: argv[2], adapterSha256: argv[3] };
    }
    throw new Error('Use --preflight <approved-adapter-sha256> or --preflight --repo <exact-repository> <approved-adapter-sha256>');
  }
  let repository = REPO;
  let repositoryExplicit = false;
  let issue = null;
  let commentId = null;
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!['--repo', '--issue', '--comment-id'].includes(key) || typeof value !== 'string' || value.startsWith('--')) {
      throw new Error('Use --repo <exact-repository> with optional --issue <number> --comment-id <number>');
    }
    if (key === '--repo') {
      if (repositoryExplicit) throw new Error('Select the repository once');
      requireDispatchRepo(value);
      repository = value;
      repositoryExplicit = true;
    } else {
      if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) < 1) {
        throw new Error(key + ' must be a positive integer');
      }
      if (key === '--issue') {
        if (issue !== null) throw new Error('Select the issue once');
        issue = Number(value);
      } else {
        if (commentId !== null) throw new Error('Select the comment once');
        commentId = Number(value);
      }
    }
    index += 1;
  }
  if ((issue === null) !== (commentId === null) || (issue !== null && !repositoryExplicit)) {
    throw new Error('A live target requires --repo, --issue, and --comment-id');
  }
  return { preflight: false, repository, repositoryExplicit, issue, commentId };
}

export async function main(env = process.env, argv = process.argv.slice(2)) {
  const selection = parseReceiverArgs(argv);
  if (selection.preflight) {
    hostPreflight({ adapterSha256: selection.adapterSha256, repository: selection.repository, env });
    console.log('Host preflight ready; no event consumed and no provider request made.');
    return;
  }
  const repository = selection.repository;
  const liveEnabled = env.VERA_DEEPSEEK_LIVE_ENABLED === 'true';
  if (selection.issue !== null && !liveEnabled) {
    throw new Error('Explicit issue/comment selection is only valid for an enabled live poll');
  }
  if (selection.issue !== null && repository === REPO) {
    throw new Error('Timeline live targets continue to use the existing exact issue/comment environment variables');
  }
  let liveTarget = { issue: Number(env.VERA_DEEPSEEK_LIVE_ISSUE), commentId: Number(env.VERA_DEEPSEEK_LIVE_COMMENT_ID) };
  if (liveEnabled && repository === RESEARCH_REPO) {
    const envIssue = Number(env.VERA_DEEPSEEK_LIVE_ISSUE);
    const envCommentId = Number(env.VERA_DEEPSEEK_LIVE_COMMENT_ID);
    if (!selection.repositoryExplicit || selection.issue === null || selection.commentId === null ||
        !Number.isSafeInteger(envIssue) || envIssue !== selection.issue ||
        !Number.isSafeInteger(envCommentId) || envCommentId !== selection.commentId) {
      throw new Error('Research live poll requires matching explicit --repo, --issue, and --comment-id selections');
    }
    liveTarget = { repository, issue: selection.issue, commentId: selection.commentId };
  } else if (liveEnabled && (!Number.isSafeInteger(liveTarget.issue) || liveTarget.issue < 1 ||
      !Number.isSafeInteger(liveTarget.commentId) || liveTarget.commentId < 1)) {
    throw new Error('Live one-shot requires the exact approved issue and dispatch comment IDs');
  }
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
    result = await pollOnce({ repository, allowedActors, liveEnabled, liveTarget });
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
