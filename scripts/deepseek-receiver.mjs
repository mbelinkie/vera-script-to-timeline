// Outbound-only Mac poller. It reads public GitHub metadata, then delegates
// only a manifest-bound request to the existing private controller.
import { createHash, randomUUID } from 'node:crypto';
import { lstatSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, isAbsolute, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { hostPreflight } from './deepseek-host-preflight.mjs';
import { liveApprovalMetadata, verifyLiveApproval, readPublicGh as readLiveGh } from './deepseek-live-gate.mjs';
import { verifyReviewFromGh } from './chat-review-github.mjs';
import { COMMAND, REPO, invokePrivateRunner, requestFromEvent, reserveReceipt, taskCap, verifyCurrentComment, verifyCurrentIssue, verifyFreshDispatch, writeReceipt } from './deepseek-dispatch.mjs';

const API = 'https://api.github.com';
const PAGE_SIZE = 100;
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

export async function listRecentComments(fetchImpl = globalThis.fetch, lastSeenId = null, lastSeenCreatedAt = null) {
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
  const response = await fetchImpl(apiUrl('/repos/' + REPO + '/issues/comments?' + query), {
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

export function readCursor(path) {
  return readCursorRecord(path)?.lastCommentId ?? null;
}

function readCursorCreatedAt(path) {
  return readCursorRecord(path)?.lastCommentCreatedAt ?? null;
}

function readCursorRecord(path) {
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
  if (cursor.lastCommentCreatedAt !== undefined &&
      (typeof cursor.lastCommentCreatedAt !== 'string' || !Number.isFinite(Date.parse(cursor.lastCommentCreatedAt)))) {
    throw new Error('Receiver cursor timestamp is invalid');
  }
  return cursor;
}

export function writeCursor(path, lastCommentId, lastCommentCreatedAt = null) {
  if (!Number.isSafeInteger(lastCommentId) || lastCommentId < 0) throw new Error('Receiver cursor is invalid');
  if (lastCommentCreatedAt !== null &&
      (typeof lastCommentCreatedAt !== 'string' || !Number.isFinite(Date.parse(lastCommentCreatedAt)))) {
    throw new Error('Receiver cursor timestamp is invalid');
  }
  const dir = dirname(path);
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  privateFile(dir, { directory: true });
  const temporary = path + '.' + randomUUID() + '.tmp';
  const cursor = { repository: REPO, lastCommentId };
  if (lastCommentCreatedAt !== null) cursor.lastCommentCreatedAt = lastCommentCreatedAt;
  writeFileSync(temporary, JSON.stringify(cursor) + '\n', { flag: 'wx', mode: 0o400 });
  renameSync(temporary, path);
}

export function liveIdentity(manifest, manifestSha) {
  return {
    issue: manifest.issue, commentId: manifest.dispatch_comment_id, manifestSha,
    sourceSha: manifest.base_sha, adapterSha: manifest.adapter_sha256,
    reconciliationSha: manifest.reconciliation_sha256, attemptId: manifest.attempt_id,
    campaign: manifest.campaign, model: manifest.model, maxOutputTokens: manifest.max_output_tokens
  };
}

export function validateManifest(manifest, issue, commentId, currentMainSha) {
  const safePath = value => typeof value === 'string' && value.length > 0 && !value.startsWith('/') &&
    !value.startsWith('~') && !value.includes('\\') && value.split('/').every(part => part && part !== '.' && part !== '..') &&
    !value.startsWith('.github/') && !value.split('').some(character => character.charCodeAt(0) < 32);
  const safeCommand = command => Array.isArray(command) && command.length >= 2 && command.length <= 12 &&
    typeof command[0] === 'string' && isAbsolute(command[0]) && command.every(part =>
      typeof part === 'string' && part.length > 0 && part.length < 300 && part !== '-c' && part !== '-e' &&
      !part.includes('/bin/sh') && !part.split('').some(character => character.charCodeAt(0) < 32));
  const frozen = manifest?.frozen_files;
  const scope = manifest?.edit_scope;
  const validScope = scope?.mode === 'full_file' ? scope.approve_entire_file === true :
    scope?.mode === 'bounded_region' && ['start_marker', 'end_marker'].every(key =>
      typeof scope[key] === 'string' && scope[key].length >= 8 && scope[key].length <= 300);
  const legacyMock = manifest?.schema === 1 && manifest.transport_contract === 'VERA_DEEPSEEK_RECEIVER_V1' &&
    (manifest.execution_mode === undefined || manifest.execution_mode === 'mock');
  const versioned = manifest?.schema === 2 && manifest.transport_contract === 'VERA_DEEPSEEK_RECEIVER_V2' &&
    ['mock', 'live'].includes(manifest.execution_mode);
  const mode = versioned ? manifest.execution_mode : 'mock';
  if (!manifest || !(legacyMock || versioned) || manifest.issue !== issue || manifest.repository !== REPO ||
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
    const metadata = liveApprovalMetadata(liveIdentity(manifest, '0'.repeat(64)));
    const age = Date.now() - Date.parse(manifest.pricing_verified_on + 'T00:00:00.000Z');
    if (manifest.live_contract !== 'VERA_DEEPSEEK_LIVE_V2' || Object.hasOwn(manifest, 'mock_replacement') ||
        Object.hasOwn(manifest, 'continuation_contract') ||
        manifest.max_rounds !== 1 || String(manifest.task_cap_usd) !== '0.25' ||
        manifest.campaign_cap_usd !== '0.25' || manifest.lifetime_cap_usd !== '10' ||
        manifest.max_input_units !== 20000 || manifest.reasoning_effort !== 'high' ||
        !SHA256.test(manifest.ledger_sha256 || '') ||
        !/^\d{4}-\d{2}-\d{2}$/.test(manifest.pricing_verified_on || '') ||
        !Number.isFinite(age) || age < 0 || age >= 8 * 86400000 ||
        JSON.stringify(manifest.verified_rates) !== JSON.stringify(metadata.verifiedRates)) {
      throw new Error('Live task requires exact approved single-attempt pricing and accounting bounds');
    }
  }
  return { cap, mode };
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
  allowedActors = [], fetchImpl = globalThis.fetch, readGh = readPublicGh,
  manifestDir = join(homedir(), '.local', 'share', 'vera', 'deepseek', 'tasks'),
  receiptRoot = join(homedir(), '.codex', 'deepseek-dispatch-receipts'),
  runner = join(homedir(), '.codex', 'bin', 'vera-deepseek-runner'),
  invoke = invokePrivateRunner, preflight = hostPreflight,
  liveEnabled = false, readLive = readLiveGh
} = {}) {
  if (comment?.body !== COMMAND) return { state: 'ignored' };
  const issueMatch = new RegExp('^https://api\\.github\\.com/repos/' + REPO.replaceAll('/', '\\/') + '/issues/(\\d+)$').exec(comment.issue_url || '');
  if (!issueMatch) return { state: 'refused' };
  const issueNumber = Number(issueMatch[1]);
  let issue;
  try {
    issue = await fetchJson('/repos/' + REPO + '/issues/' + issueNumber, fetchImpl);
  } catch (error) {
    if (isTerminalHttpError(error)) return { state: 'refused' };
    throw error;
  }
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
  if (loaded.mode === 'live' && !liveEnabled) return { state: 'refused' };
  try {
    verifyReviewFromGh(readGh, REPO, issueNumber, { title: issue.title, body: issue.body, labels: issue.labels });
  } catch (error) {
    if (/Public GitHub review read failed/.test(error.message)) throw error;
    return { state: 'refused' };
  }
  let confirmed;
  try {
    confirmed = await fetchJson('/repos/' + REPO + '/issues/' + issueNumber, fetchImpl);
  } catch (error) {
    if (isTerminalHttpError(error)) return { state: 'refused' };
    throw error;
  }
  const labels = value => (value || []).map(label => typeof label === 'string' ? label : label?.name).sort();
  if (confirmed.title !== issue.title || confirmed.body !== issue.body || confirmed.state !== issue.state ||
      JSON.stringify(labels(confirmed.labels)) !== JSON.stringify(labels(issue.labels))) return { state: 'refused' };
  let confirmedComment;
  try {
    confirmedComment = await fetchJson('/repos/' + REPO + '/issues/comments/' + comment.id, fetchImpl);
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
    verifyReviewFromGh(readGh, REPO, issueNumber, {
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
      fetchJson('/repos/' + REPO + '/issues/' + issueNumber, fetchImpl),
      fetchJson('/repos/' + REPO + '/issues/comments/' + comment.id, fetchImpl),
      fetchJson('/repos/' + REPO + '/commits/main', fetchImpl)
    ]);
  } catch (error) {
    if (isTerminalHttpError(error)) return { state: 'refused' };
    throw error;
  }
  try {
    verifyFreshDispatch({
      issue: finalIssue, comment: finalComment, currentMainSha: finalMain?.sha, request,
      actor: comment.user.login, expectedIssue: issue, expectedComment: confirmedComment,
      expectedMainSha: currentMain.sha
    });
    const finalManifest = loadApprovedManifest(manifestPath, issueNumber, comment.id, finalMain.sha);
    if (finalManifest.sha256 !== loaded.sha256) throw new Error('Private task manifest changed');
    safeRunner(runner, finalManifest.manifest.adapter_sha256);
    preflight({ runner, adapterSha256: finalManifest.manifest.adapter_sha256, receiptRoot, allowEnabled: true });
    if (loaded.mode === 'live') verifyLiveApproval(readLive, liveIdentity(finalManifest.manifest, finalManifest.sha256));
    // Public reads may take time; repeat local manifest/build checks after them.
    const beforeInvoke = loadApprovedManifest(manifestPath, issueNumber, comment.id, finalMain.sha);
    if (beforeInvoke.sha256 !== loaded.sha256) throw new Error('Private task manifest changed');
    safeRunner(runner, beforeInvoke.manifest.adapter_sha256);
  } catch {
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
      : reserveReceipt(receiptRoot, issueNumber, comment.id);
  } catch (error) {
    if (error?.code === 'EEXIST') return { state: 'duplicate' };
    throw error;
  }
  const childEnv = {
    HOME: homedir(), PATH: '/usr/bin:/bin', VERA_REPOSITORY: REPO,
    VERA_ISSUE_NUMBER: String(issueNumber), VERA_DISPATCH_COMMENT_ID: String(comment.id),
    VERA_DEEPSEEK_TASK_CAP_USD: String(loaded.cap), VERA_DEEPSEEK_CAMPAIGN_CAP_USD: '10',
    VERA_DEEPSEEK_RECEIPT: receipt, VERA_DEEPSEEK_MANIFEST_SHA256: loaded.sha256,
    VERA_DEEPSEEK_SOURCE_SHA: loaded.manifest.base_sha, VERA_DEEPSEEK_EXECUTION_MODE: loaded.mode,
    VERA_DEEPSEEK_ADAPTER_SHA256: loaded.manifest.adapter_sha256,
    ...(loaded.mode === 'live' ? { VERA_DEEPSEEK_LIVE_ENABLED: 'true' } : {})
  };
  const result = invoke(runner, [String(issueNumber), String(comment.id)], childEnv);
  const state = result.error || result.status !== 0 ? 'uncertain-or-failed' : 'worker-returned';
  if (loaded.mode === 'mock') writeReceipt(receipt, { issue: issueNumber, commentId: comment.id, state,
    timestamp: new Date().toISOString(), exitCode: result.status ?? null,
    detail: result.error?.code || null });
  return { state };
}

export async function pollOnce({
  fetchImpl = globalThis.fetch,
  cursorPath = join(homedir(), '.codex', 'deepseek-receiver', 'cursor.json'),
  allowedActors = [],
  processComment = comment => processDispatchComment(comment, { allowedActors, fetchImpl }),
  read = readCursor,
  readCreatedAt = readCursorCreatedAt,
  write = writeCursor,
  list
} = {}) {
  const lastSeen = read(cursorPath);
  let lastSeenCreatedAt = readCreatedAt(cursorPath);
  const useDefaultList = list === undefined;
  if (lastSeen !== null && lastSeenCreatedAt === null) {
    if (lastSeen === 0) {
      lastSeenCreatedAt = '1970-01-01T00:00:00.000Z';
    } else if (useDefaultList) {
      try {
        const anchor = await fetchJson('/repos/' + REPO + '/issues/comments/' + lastSeen, fetchImpl);
        if (anchor?.id !== lastSeen || typeof anchor.created_at !== 'string' || !Number.isFinite(Date.parse(anchor.created_at))) {
          throw new Error('Receiver cursor anchor is invalid');
        }
        lastSeenCreatedAt = anchor.created_at;
        write(cursorPath, lastSeen, lastSeenCreatedAt);
      } catch (error) {
        if (error?.status === 404 || error?.status === 410) {
          throw new Error('Receiver cursor anchor was deleted; manual cursor recovery is required', { cause: error });
        }
        throw error;
      }
    }
  }
  const listComments = list || ((lastSeenId, createdAt) => listRecentComments(fetchImpl, lastSeenId, createdAt));
  const comments = await listComments(lastSeen, lastSeenCreatedAt);
  if (!Array.isArray(comments) || !comments.every(comment => Number.isSafeInteger(comment?.id) && comment.id > 0) ||
      new Set(comments.map(comment => comment.id)).size !== comments.length) {
    throw new Error('GitHub comment history is incomplete');
  }
  if (lastSeen === null) {
    const latest = comments.reduce((current, comment) => !current || comment.id > current.id ? comment : current, null);
    write(cursorPath, latest?.id ?? 0, latest?.created_at ?? (latest ? null : '1970-01-01T00:00:00.000Z'));
    return { initialized: true, processed: 0 };
  }
  const ordered = comments.filter(comment => comment.id > lastSeen).sort((left, right) => left.id - right.id);
  for (const comment of ordered) {
    await processComment(comment);
    write(cursorPath, comment.id, comment.created_at ?? null);
  }
  return { initialized: false, processed: ordered.length };
}

export async function main(env = process.env, argv = process.argv.slice(2)) {
  if (argv[0] === '--preflight' && argv.length === 2) {
    hostPreflight({ adapterSha256: argv[1], env });
    console.log('Host preflight ready; no event consumed and no provider request made.');
    return;
  }
  if (argv.length) throw new Error('Use --preflight <approved-adapter-sha256>, or no arguments for one poll');
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
    result = await pollOnce({ allowedActors, processComment: comment => processDispatchComment(comment, {
      allowedActors, liveEnabled: env.VERA_DEEPSEEK_LIVE_ENABLED === 'true'
    }) });
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
