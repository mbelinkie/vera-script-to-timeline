import { accessSync, closeSync, constants, fstatSync, lstatSync, openSync, readFileSync } from 'node:fs';
import { Buffer } from 'node:buffer';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { homedir } from 'node:os';
import { basename, dirname, isAbsolute, join } from 'node:path';
import { REPO, requireDispatchRepo } from './deepseek-dispatch.mjs';

const SHA256 = /^[a-f0-9]{64}$/;
const OUTPUT_LIMIT = 16 * 1024;
const SYSTEM_PATH = '/usr/bin:/bin';
const RECEIPT_ROOT = join(homedir(), '.codex', 'deepseek-dispatch-receipts');
const CURSOR_PATH = join(homedir(), '.codex', 'deepseek-receiver', 'cursor.json');
const ENABLE_FLAGS = [
  'VERA_DEEPSEEK_DISPATCH_ENABLED',
  'VERA_DEEPSEEK_LIVE_ENABLED',
  'VERA_DEEPSEEK_CONTINUATION_ENABLED',
  'VERA_DEEPSEEK_QUALITY_LIVE_ENABLED',
  'CONTINUATION_ENABLED',
  'QUALITY_LIVE_ENABLED'
];
const PREFLIGHT_RESULT = {
  contract: 'VERA_DEEPSEEK_HOST_PREFLIGHT_V1',
  ready: true,
  adapterSha256: null,
  defaultMode: 'disabled',
  isolation: 'seatbelt',
  accounting: 'shared-lifetime-ledger'
};

function refuse(message) {
  throw new Error(message);
}

function requireAbsolute(value, description) {
  if (typeof value !== 'string' || value.length === 0 || !isAbsolute(value)) {
    refuse(`${description} must be an absolute path.`);
  }
  return value;
}

function ownedByCurrentUser(stat) {
  const uid = process.getuid?.();
  return Number.isInteger(uid) && stat.uid === uid;
}

function checkDirectory(path, message) {
  let stat;
  try {
    stat = lstatSync(path);
  } catch {
    refuse(message);
  }
  if (stat.isSymbolicLink() || !stat.isDirectory() || !ownedByCurrentUser(stat) ||
      (stat.mode & 0o077) !== 0 || (stat.mode & 0o700) !== 0o700) {
    refuse(message);
  }
  try {
    accessSync(path, constants.R_OK | constants.W_OK | constants.X_OK);
  } catch {
    refuse(message);
  }
}

function checkCursor(path) {
  let stat;
  try {
    stat = lstatSync(path);
  } catch (error) {
    if (error?.code === 'ENOENT') return;
    refuse('Receiver cursor file is unavailable; repair its location before enabling dispatch.');
  }
  const message = 'Receiver cursor file must be an owner-only regular file that is readable and safely replaceable.';
  if (stat.isSymbolicLink() || !stat.isFile() || !ownedByCurrentUser(stat) ||
      (stat.mode & 0o077) !== 0 || (stat.mode & 0o222) !== 0 || (stat.mode & 0o400) !== 0o400) {
    refuse(message);
  }
  try {
    accessSync(path, constants.R_OK);
  } catch {
    refuse(message);
  }
}

function runnerSha256(path) {
  const message = 'Installed private runner must be an owner-only executable regular file.';
  let stat;
  try {
    stat = lstatSync(path);
  } catch {
    refuse('Installed private runner is unavailable; install the approved host runner before enabling dispatch.');
  }
  if (stat.isSymbolicLink() || !stat.isFile() || !ownedByCurrentUser(stat) ||
      (stat.mode & 0o077) !== 0 || (stat.mode & 0o500) !== 0o500) {
    refuse(message);
  }
  try {
    accessSync(path, constants.R_OK | constants.X_OK);
  } catch {
    refuse(message);
  }

  let fd;
  try {
    const noFollow = constants.O_NOFOLLOW ?? 0;
    fd = openSync(path, constants.O_RDONLY | noFollow);
    const opened = fstatSync(fd);
    if (!opened.isFile() || !ownedByCurrentUser(opened) ||
        (opened.mode & 0o077) !== 0 || (opened.mode & 0o500) !== 0o500 ||
        opened.dev !== stat.dev || opened.ino !== stat.ino) {
      refuse(message);
    }
    const bytes = readFileSync(fd);
    const after = fstatSync(fd);
    if (!after.isFile() || after.dev !== opened.dev || after.ino !== opened.ino ||
        after.size !== opened.size || after.mtimeMs !== opened.mtimeMs) {
      refuse('Installed private runner changed while it was being checked; retry after restoring the approved runner.');
    }
    return createHash('sha256').update(bytes).digest('hex');
  } catch (error) {
    if (error instanceof Error && error.message.startsWith('Installed private runner')) throw error;
    refuse(message);
  } finally {
    if (fd !== undefined) closeSync(fd);
  }
}

function verifyDirectories(receiptRoot, cursorPath) {
  checkDirectory(dirname(receiptRoot), 'Receipt storage parent must exist and be owner-only, readable, and writable.');
  checkDirectory(receiptRoot, 'Receipt storage must exist and be owner-only, readable, and writable.');
  checkDirectory(dirname(cursorPath), 'Receiver cursor directory must exist and be owner-only, readable, and writable.');
  checkCursor(cursorPath);
}

const REFUSAL_MESSAGES = {
  STATE_PERMISSIONS: 'Private host preflight refused unsafe receiver-state permissions; make the state directories owner-only and owned by the current user.',
  STATE_ACCESS: 'Private host preflight refused unavailable receiver-state storage; restore owner read/write access to the required state directories.',
  ADAPTER_BUILD: 'Private host preflight refused the installed adapter build; restore the approved DeepSeek adapter build.',
  ACCOUNTING: 'Private host preflight refused shared lifetime accounting; restore the owner-only accounting ledger before enabling dispatch.',
  ISOLATION: 'Private host preflight refused macOS Seatbelt isolation; restore sandbox-exec availability and retry.'
};

function verifyChildResult(result, adapterSha256) {
  if (!result || result.error || result.signal || !Number.isSafeInteger(result.status) || result.status < 0 ||
      typeof result.stdout !== 'string' || typeof (result.stderr ?? '') !== 'string' ||
      Buffer.byteLength(result.stdout, 'utf8') > OUTPUT_LIMIT ||
      Buffer.byteLength(result.stderr ?? '', 'utf8') > OUTPUT_LIMIT) {
    refuse('Private host preflight did not complete successfully; repair the approved runner and retry.');
  }
  let payload;
  try {
    payload = JSON.parse(result.stdout);
  } catch {
    refuse('Private host preflight returned an invalid contract; reinstall the approved runner and retry.');
  }
  const refusalKeys = ['contract', 'ready', 'reason'].sort();
  if (payload && typeof payload === 'object' && !Array.isArray(payload) &&
      Object.keys(payload).sort().join('\0') === refusalKeys.join('\0') &&
      payload.contract === 'VERA_DEEPSEEK_HOST_PREFLIGHT_V1' && payload.ready === false) {
    const message = REFUSAL_MESSAGES[payload.reason];
    if (message) refuse(message);
  }
  const expected = { ...PREFLIGHT_RESULT, adapterSha256 };
  const keys = Object.keys(expected).sort();
  if (result.status !== 0 || !payload || typeof payload !== 'object' || Array.isArray(payload) ||
      Object.keys(payload).sort().join('\0') !== keys.join('\0') ||
      keys.some(key => payload[key] !== expected[key])) {
    refuse('Private host preflight contract is not ready; restore the matching runner and host isolation before enabling dispatch.');
  }
  return expected;
}

export function hostPreflight({
  runner = join(homedir(), '.codex', 'bin', 'vera-deepseek-runner'),
  adapterSha256,
  receiptRoot,
  cursorPath,
  repository = REPO,
  env = process.env,
  spawn = spawnSync,
  allowEnabled = false
} = {}) {
  const slug = requireDispatchRepo(repository);
  if (receiptRoot === undefined) {
    receiptRoot = repository === REPO ? RECEIPT_ROOT : join(RECEIPT_ROOT, slug);
  }
  if (cursorPath === undefined) {
    cursorPath = repository === REPO ? CURSOR_PATH : join(dirname(CURSOR_PATH), slug, basename(CURSOR_PATH));
  }
  runner = requireAbsolute(runner, 'Private runner path');
  receiptRoot = requireAbsolute(receiptRoot, 'Receipt directory path');
  cursorPath = requireAbsolute(cursorPath, 'Receiver cursor path');
  if (typeof adapterSha256 !== 'string' || !SHA256.test(adapterSha256)) {
    refuse('Expected adapter SHA-256 must be a lowercase 64-character hash.');
  }
  if (!env || typeof env !== 'object') refuse('Host environment is unavailable; retry from the receiver process.');
  if (allowEnabled !== true && allowEnabled !== false) refuse('Host preflight activation mode must be explicitly true or false.');
  if (!allowEnabled && ENABLE_FLAGS.some(flag => env[flag] === 'true')) {
    refuse('Live DeepSeek, continuation, or quality flags are enabled during publication preflight; disable them and retry.');
  }

  verifyDirectories(receiptRoot, cursorPath);
  if (runnerSha256(runner) !== adapterSha256) {
    refuse('Installed private runner SHA-256 does not match the approved adapter; restore the matching runner.');
  }

  const home = typeof env.HOME === 'string' && env.HOME.length > 0 ? env.HOME : homedir();
  let child;
  try {
    child = spawn(runner, ['--host-preflight'], {
      env: { HOME: home, PATH: SYSTEM_PATH, VERA_DEEPSEEK_ADAPTER_SHA256: adapterSha256,
        ...(repository === REPO ? {} : { VERA_REPOSITORY: repository }) },
      encoding: 'utf8',
      maxBuffer: OUTPUT_LIMIT,
      shell: false,
      stdio: 'pipe',
      timeout: 30_000
    });
  } catch {
    refuse('Private host preflight could not start; verify the approved runner is installed and executable.');
  }
  const safeResult = verifyChildResult(child, adapterSha256);
  if (runnerSha256(runner) !== adapterSha256) {
    refuse('Installed private runner changed during host preflight; restore the approved runner before retrying.');
  }
  return safeResult;
}
