// #510 phase 2: code-only, manual-first Test Bench terminal event capture.
// No worker integration, chat senders, CI queue mutation, or native effects.
import { Buffer } from 'node:buffer';
import {
  createCipheriv, createDecipheriv, createHash, createHmac, hkdfSync,
  randomBytes, randomUUID, timingSafeEqual,
} from 'node:crypto';
import {
  closeSync, constants, existsSync, fstatSync, fsyncSync, lstatSync, mkdirSync,
  openSync, readFileSync, renameSync, unlinkSync, writeSync,
} from 'node:fs';
import path from 'node:path';

const RECEIPT_DOMAIN = 'vera.test-bench.terminal-receipt/v1';
const EVENT_DOMAIN = 'vera.test-bench.immutable-terminal-event/v1';
const STATUSES = new Set(['VERIFIED', 'FAILED', 'BLOCKED', 'UNKNOWN', 'CANCELED', 'EXPIRED']);
const STAGES = ['pristine', 'edited', 'revision', 'rebuild'];
const SHA = /^[a-f0-9]{64}$/;
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/;
const REPO = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
const ARTIFACT = /^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/;
const MAX_RECEIPT_BYTES = 64 * 1024;
const MAX_RECEIPT_LIFETIME_MS = 5 * 60 * 1000;
const CLOCK_SKEW_MS = 30 * 1000;

function fields(value, keys, label) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)
      || (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)
      || Object.keys(value).length !== keys.length
      || keys.some(key => !Object.hasOwn(value, key))) throw new Error(`Invalid ${label} fields`);
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function clone(value) { return JSON.parse(canonical(value)); }
function sha(value) { return createHash('sha256').update(value).digest('hex'); }
function assertSha(value, label) { if (typeof value !== 'string' || !SHA.test(value)) throw new Error(`Invalid ${label} SHA-256`); }
function assertId(value, label) { if (typeof value !== 'string' || !ID.test(value)) throw new Error(`Invalid ${label}`); }
function key(value, label) { if (!Buffer.isBuffer(value) || value.length < 32) throw new Error(`${label} needs a private 32+ byte Buffer`); return value; }
function hmac(domain, value, secret) { return createHmac('sha256', secret).update(domain).update('\0').update(canonical(value)).digest('hex'); }
function macMatches(domain, value, signature, secret) {
  return typeof signature === 'string' && SHA.test(signature)
    && timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(hmac(domain, value, secret), 'hex'));
}
function validTime(value) { return Number.isSafeInteger(value) && value > 0; }

function validateTerminal(t) {
  fields(t, [
    'repository', 'issueNumber', 'pullNumber', 'jobId', 'caseId', 'attemptId', 'operationId',
    'sourceSha256', 'actorSha256', 'correlationId', 'bindingId', 'outcome', 'reasonCode',
    'stageReceipts', 'report', 'strict312',
  ], 'terminal result');
  if (typeof t.repository !== 'string' || !REPO.test(t.repository)
      || !Number.isSafeInteger(t.issueNumber) || t.issueNumber < 1
      || (t.pullNumber !== null && (!Number.isSafeInteger(t.pullNumber) || t.pullNumber < 1))) {
    throw new Error('Invalid repository or issue/PR identity');
  }
  for (const name of ['jobId', 'caseId', 'attemptId', 'operationId', 'reasonCode']) assertId(t[name], name);
  for (const name of ['sourceSha256', 'actorSha256']) assertSha(t[name], name);
  if (!UUID.test(t.correlationId) || !UUID.test(t.bindingId)) throw new Error('Invalid opaque origin correlation/binding');
  if (!STATUSES.has(t.outcome)) throw new Error('Invalid terminal outcome');
  if (t.strict312 !== null) throw new Error('Strict #312 acceptance is unproved by these code-only receipts');
  if (!Array.isArray(t.stageReceipts) || t.stageReceipts.length > STAGES.length) {
    throw new Error('Invalid stage receipts');
  }
  let prior = -1;
  for (const receipt of t.stageReceipts) {
    fields(receipt, ['stage', 'sha256'], 'stage digest');
    const index = STAGES.indexOf(receipt.stage);
    if (index <= prior) throw new Error('Duplicate, unordered or unknown stage receipt');
    prior = index;
    assertSha(receipt.sha256, 'stage receipt');
  }
  fields(t.report, ['artifactId', 'sha256'], 'report pointer');
  if (typeof t.report.artifactId !== 'string' || !ARTIFACT.test(t.report.artifactId)
      || t.report.artifactId.split('/').includes('..')) throw new Error('Invalid report artifact pointer');
  assertSha(t.report.sha256, 'report');
}

// Only trusted, independently authenticated verifier adapters may sign.
// This helper is exposed to construct *test* fixtures; do not expose it as
// an endpoint accepting AI text, case output, or unscreened runner data.
export function signTerminalAttestation(unsigned, receiptSigningKey) {
  key(receiptSigningKey, 'Receipt signing key');
  const payload = clone(unsigned);
  delete payload.signature;
  return { ...payload, signature: hmac(RECEIPT_DOMAIN, payload, receiptSigningKey) };
}

function validateAttestation(input, trustedIssuers, now) {
  fields(input, ['version', 'issuer', 'provenance', 'issuedAt', 'expiresAt', 'terminal', 'signature'], 'terminal attestation');
  if (input.version !== 1 || !['simulation', 'signed-read-only'].includes(input.provenance)) {
    throw new Error('Invalid terminal attestation version/provenance');
  }
  assertId(input.issuer, 'issuer');
  const trusted = trustedIssuers.get(input.issuer);
  if (!trusted || trusted.provenance !== input.provenance) throw new Error('Untrusted terminal receipt issuer/provenance');
  if (!validTime(input.issuedAt) || !validTime(input.expiresAt)
      || input.expiresAt <= input.issuedAt
      || input.expiresAt - input.issuedAt > MAX_RECEIPT_LIFETIME_MS
      || input.issuedAt > now + CLOCK_SKEW_MS || input.expiresAt <= now) {
    throw new Error('Expired, future or invalid signed terminal receipt');
  }
  validateTerminal(input.terminal);
  const { signature, ...payload } = input;
  if (!macMatches(RECEIPT_DOMAIN, payload, signature, trusted.key)) {
    throw new Error('Invalid terminal receipt signature');
  }
  return clone(input);
}

function attemptKey(t) { return sha(canonical([t.repository, t.issueNumber, t.jobId, t.caseId, t.attemptId])); }

function buildEvent(receipt, eventKey) {
  const content = {
    version: 1, eventKind: 'test-bench.terminal', provenance: receipt.provenance,
    issuer: receipt.issuer, receiptSha256: sha(canonical(receipt)),
    repository: receipt.terminal.repository, issueNumber: receipt.terminal.issueNumber,
    pullNumber: receipt.terminal.pullNumber, jobId: receipt.terminal.jobId,
    caseId: receipt.terminal.caseId, attemptId: receipt.terminal.attemptId,
    operationId: receipt.terminal.operationId, sourceSha256: receipt.terminal.sourceSha256,
    actorSha256: receipt.terminal.actorSha256, correlationId: receipt.terminal.correlationId,
    bindingId: receipt.terminal.bindingId, outcome: receipt.terminal.outcome,
    reasonCode: receipt.terminal.reasonCode, stageReceipts: receipt.terminal.stageReceipts,
    report: receipt.terminal.report, strict312Verdict: 'UNPROVED',
    acceptanceAuthority: 'none',
  };
  const eventId = sha(`${EVENT_DOMAIN}\0${canonical(content)}`);
  return { ...content, eventId, signature: hmac(EVENT_DOMAIN, { ...content, eventId }, eventKey) };
}

function validateEvent(event, eventKey) {
  const { eventId, signature, ...content } = event;
  if (typeof eventId !== 'string' || !SHA.test(eventId)
      || eventId !== sha(`${EVENT_DOMAIN}\0${canonical(content)}`)
      || !macMatches(EVENT_DOMAIN, { ...content, eventId }, signature, eventKey)) {
    throw new Error('Immutable terminal event integrity check failed');
  }
  if (content.strict312Verdict !== 'UNPROVED' || content.acceptanceAuthority !== 'none') {
    throw new Error('Unauthorized strict #312 acceptance authority');
  }
  validateTerminal({
    repository: content.repository, issueNumber: content.issueNumber, pullNumber: content.pullNumber,
    jobId: content.jobId, caseId: content.caseId, attemptId: content.attemptId,
    operationId: content.operationId, sourceSha256: content.sourceSha256,
    actorSha256: content.actorSha256, correlationId: content.correlationId,
    bindingId: content.bindingId, outcome: content.outcome, reasonCode: content.reasonCode,
    stageReceipts: content.stageReceipts, report: content.report, strict312: null,
  });
}

function ensureDir(directory) {
  if (!existsSync(directory)) mkdirSync(directory, { recursive: true, mode: 0o700 });
  const s = lstatSync(directory);
  if (!s.isDirectory() || s.isSymbolicLink() || (s.mode & 0o777) !== 0o700
      || (process.getuid && s.uid !== process.getuid())) throw new Error('Unsafe private outbox directory');
}
function regular(file) {
  let s;
  try { s = lstatSync(file); } catch (e) { if (e.code === 'ENOENT') return false; throw e; }
  if (!s.isFile() || s.isSymbolicLink() || (s.mode & 0o777) !== 0o600 || s.nlink !== 1
      || (process.getuid && s.uid !== process.getuid())) throw new Error('Unsafe private outbox file');
  return true;
}
function emptyState() { return { version: 1, events: {}, attempts: {}, audit: {} }; }
function validateState(s, eventKey) {
  fields(s, ['version', 'events', 'attempts', 'audit'], 'outbox state');
  if (s.version !== 1) throw new Error('Unknown outbox version');
  for (const name of ['events', 'attempts', 'audit']) {
    if (!s[name] || typeof s[name] !== 'object' || Array.isArray(s[name])) throw new Error('Invalid outbox state');
  }
  for (const [eventId, event] of Object.entries(s.events)) {
    validateEvent(event, eventKey);
    if (eventId !== event.eventId || s.attempts[attemptKey(event)] !== eventId) {
      throw new Error('Outbox event/attempt index mismatch');
    }
    const audit = s.audit[eventId];
    fields(audit, ['eventId', 'status', 'firstPersistedAt', 'history'], 'outbox audit');
    if (audit.eventId !== eventId || audit.status !== 'persisted'
        || !validTime(audit.firstPersistedAt) || !Array.isArray(audit.history)
        || audit.history.length !== 1 || audit.history[0].state !== 'persisted'
        || audit.history[0].at !== audit.firstPersistedAt) throw new Error('Outbox audit integrity failure');
  }
  for (const [attempt, eventId] of Object.entries(s.attempts)) {
    if (!Object.hasOwn(s.events, eventId) || attemptKey(s.events[eventId]) !== attempt) {
      throw new Error('Orphan outbox attempt index');
    }
  }
  if (Object.keys(s.audit).length !== Object.keys(s.events).length
      || Object.keys(s.attempts).length !== Object.keys(s.events).length) {
    throw new Error('Outbox index/audit count mismatch');
  }
}

function load(file, encryptionKey, eventKey) {
  if (!regular(file)) return emptyState();
  try {
    const envelope = JSON.parse(readFileSync(file, 'utf8'));
    fields(envelope, ['version', 'iv', 'ciphertext', 'tag'], 'encrypted outbox');
    if (envelope.version !== 1 || !/^[a-f0-9]{24}$/.test(envelope.iv)
        || !/^[a-f0-9]{32}$/.test(envelope.tag)
        || !/^(?:[a-f0-9]{2})+$/.test(envelope.ciphertext)) throw new Error('Invalid encrypted encoding');
    const decipher = createDecipheriv('aes-256-gcm', encryptionKey, Buffer.from(envelope.iv, 'hex'));
    decipher.setAuthTag(Buffer.from(envelope.tag, 'hex'));
    const plain = Buffer.concat([decipher.update(Buffer.from(envelope.ciphertext, 'hex')), decipher.final()]);
    const state = JSON.parse(plain.toString('utf8'));
    validateState(state, eventKey);
    return state;
  } catch {
    throw new Error('Private terminal outbox integrity failure: refuse reset');
  }
}
function save(file, encryptionKey, state) {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', encryptionKey, iv);
  const encrypted = Buffer.concat([cipher.update(canonical(state), 'utf8'), cipher.final()]);
  const document = JSON.stringify({ version: 1, iv: iv.toString('hex'),
    ciphertext: encrypted.toString('hex'), tag: cipher.getAuthTag().toString('hex') }) + '\n';
  const tmp = `${file}.${randomUUID()}.tmp`;
  let fd;
  try {
    fd = openSync(tmp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    writeSync(fd, document); fsyncSync(fd); closeSync(fd); fd = undefined;
    renameSync(tmp, file);
    const dir = openSync(path.dirname(file), constants.O_RDONLY);
    try { fsyncSync(dir); } finally { closeSync(dir); }
  } finally {
    if (fd !== undefined) closeSync(fd);
    if (existsSync(tmp)) unlinkSync(tmp);
  }
}

export function createTerminalOutbox({ filePath, receiptKeys, eventKey, encryptionKey, now = Date.now }) {
  if (typeof filePath !== 'string' || !path.isAbsolute(filePath)) throw new Error('Outbox path must be absolute');
  key(eventKey, 'Event signing key'); key(encryptionKey, 'Outbox encryption key');
  if (!receiptKeys || typeof receiptKeys !== 'object' || Array.isArray(receiptKeys)
      || !Object.keys(receiptKeys).length) throw new Error('Trusted receipt issuers are required');
  const issuers = new Map(Object.entries(receiptKeys).map(([issuer, entry]) => {
    assertId(issuer, 'issuer');
    fields(entry, ['provenance', 'key'], 'receipt issuer authority');
    if (!['simulation', 'signed-read-only'].includes(entry.provenance)) throw new Error('Invalid issuer provenance');
    return [issuer, { provenance: entry.provenance, key: key(entry.key, 'Receipt authority key') }];
  }));
  const atRestKey = Buffer.from(hkdfSync('sha256', encryptionKey,
    Buffer.from('vera-510-terminal-outbox'), Buffer.from('aes-256-gcm/outbox/v1'), 32));

  function withState(write, operation) {
    ensureDir(path.dirname(filePath));
    const lockPath = `${filePath}.lock`;
    let fd;
    try { fd = openSync(lockPath, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600); }
    catch { throw new Error('Private terminal outbox locked; no lock stealing'); }
    try {
      const state = load(filePath, atRestKey, eventKey);
      const result = operation(state);
      if (write) save(filePath, atRestKey, state);
      return result;
    } finally { closeSync(fd); unlinkSync(lockPath); }
  }

  function persist(signedReceipt, expectedProvenance) {
    const receipt = validateAttestation(signedReceipt, issuers, now());
    if (receipt.provenance !== expectedProvenance) throw new Error('Wrong signed terminal input route');
    const event = buildEvent(receipt, eventKey);
    const attempt = attemptKey(event);
    return withState(false, state => {
      const existingId = state.attempts[attempt];
      if (existingId) {
        if (existingId !== event.eventId) throw new Error('Conflicting terminal event for same case attempt');
        return { eventId: existingId, duplicate: true, status: state.audit[existingId].status };
      }
      state.events[event.eventId] = event;
      state.attempts[attempt] = event.eventId;
      const time = now();
      state.audit[event.eventId] = { eventId: event.eventId, status: 'persisted',
        firstPersistedAt: time, history: [{ state: 'persisted', at: time }] };
      validateState(state, eventKey);
      save(filePath, atRestKey, state);
      return { eventId: event.eventId, duplicate: false, status: 'persisted' };
    });
  }

  function ingestSignedFixture({ fixturePath, sha256 }) {
    if (typeof fixturePath !== 'string' || !path.isAbsolute(fixturePath)) throw new Error('Fixture path must be absolute');
    assertSha(sha256, 'pinned fixture');
    // Open once with O_NOFOLLOW and pin the descriptor: no stat/read symlink
    // swap may redirect a historical read-only fixture to another file.
    let fd;
    let raw;
    try {
      fd = openSync(fixturePath, constants.O_RDONLY | constants.O_NOFOLLOW);
      const stat = fstatSync(fd);
      if (!stat.isFile() || stat.size > MAX_RECEIPT_BYTES || stat.nlink !== 1) {
        throw new Error('Unsafe or oversized read-only signed fixture');
      }
      raw = readFileSync(fd);
      if (raw.length > MAX_RECEIPT_BYTES) throw new Error('Oversized signed fixture');
    } catch (error) {
      if (error.code === 'ELOOP') throw new Error('Unsafe read-only signed fixture symlink', { cause: error });
      throw error;
    } finally {
      if (fd !== undefined) closeSync(fd);
    }
    if (sha(raw) !== sha256) throw new Error('Signed fixture digest mismatch');
    const parsed = JSON.parse(raw.toString('utf8'));
    if (canonical(parsed) + '\n' !== raw.toString('utf8')) throw new Error('Signed fixture must be exact canonical immutable JSON');
    return persist(parsed, 'signed-read-only');
  }

  function inspect(eventId) {
    assertSha(eventId, 'event ID');
    return withState(false, state => {
      if (!Object.hasOwn(state.events, eventId)) return null;
      return clone({ event: state.events[eventId], audit: state.audit[eventId] });
    });
  }

  return Object.freeze({
    ingestSimulation: receipt => persist(receipt, 'simulation'),
    ingestSignedFixture, inspect,
  });
}
