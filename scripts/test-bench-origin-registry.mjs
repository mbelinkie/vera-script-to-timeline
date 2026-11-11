// #510 phase 1: private, authenticated destination binding. Code-only: this
// module never sends messages, resumes threads, or invokes native Test Bench.
//
// The trusted platform adapter (not a chat message or a Test Bench report)
// must prove the real owner/thread ID before signing a register assertion.
// The future sender adapter must obtain a fresh, independently authorized
// resolve assertion; correlation IDs are locators, never bearer capabilities.
import { Buffer } from 'node:buffer';
import {
  createCipheriv, createDecipheriv, createHmac, hkdfSync, randomBytes,
  randomUUID, timingSafeEqual,
} from 'node:crypto';
import {
  closeSync, constants, existsSync, fsyncSync, lstatSync, mkdirSync,
  openSync, readFileSync, renameSync, unlinkSync, writeSync,
} from 'node:fs';
import path from 'node:path';

const AUDIENCE = 'vera.test-bench.exact-thread-origin.v1';
const SCOPE = 'test-bench.terminal-result-delivery';
const PLATFORMS = new Set(['codex', 'zodex', 'chatgpt']);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SHA256 = /^[0-9a-f]{64}$/i;
const IDENTIFIER = /^[a-zA-Z0-9][a-zA-Z0-9_.:@-]{0,255}$/;
const REPOSITORY = /^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/;
const PRIVATE_FILE_MODE = 0o600;
const PRIVATE_DIR_MODE = 0o700;
const MAX_ASSERTION_LIFETIME_MS = 5 * 60 * 1000;
const MAX_CLOCK_SKEW_MS = 30 * 1000;

function exactObject(value, fields, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)
      || Object.keys(value).length !== fields.length
      || fields.some(field => !Object.hasOwn(value, field))) {
    throw new Error(`Invalid ${label} fields`);
  }
}

function assertIdentifier(value, label) {
  if (typeof value !== 'string' || !IDENTIFIER.test(value)) throw new Error(`Invalid ${label}`);
}

function validateBinding(binding) {
  exactObject(binding, [
    'platform', 'ownerId', 'threadId', 'repository', 'issueNumber', 'pullNumber',
    'jobId', 'caseId', 'operationId', 'sourceSha256', 'actorSha256',
    'authorizationScope', 'authorizationExpiresAt', 'callbackRoute', 'correlationId',
  ], 'origin binding');
  if (!PLATFORMS.has(binding.platform)) throw new Error('Invalid platform');
  for (const field of ['ownerId', 'threadId', 'jobId', 'caseId', 'operationId']) {
    assertIdentifier(binding[field], field);
  }
  if (typeof binding.repository !== 'string' || !REPOSITORY.test(binding.repository)) {
    throw new Error('Invalid repository');
  }
  if (!Number.isSafeInteger(binding.issueNumber) || binding.issueNumber < 1
      || (binding.pullNumber !== null
        && (!Number.isSafeInteger(binding.pullNumber) || binding.pullNumber < 1))) {
    throw new Error('Invalid issue/pull number');
  }
  if (typeof binding.sourceSha256 !== 'string' || !SHA256.test(binding.sourceSha256)
      || typeof binding.actorSha256 !== 'string' || !SHA256.test(binding.actorSha256)) {
    throw new Error('Invalid source or actor hash');
  }
  if (!UUID.test(binding.correlationId)) throw new Error('Invalid correlation ID');
  if (binding.authorizationScope !== SCOPE) throw new Error('Invalid authorization scope');
  if (!Number.isSafeInteger(binding.authorizationExpiresAt) || binding.authorizationExpiresAt <= 0) {
    throw new Error('Invalid authorization expiry');
  }
  const route = binding.callbackRoute;
  exactObject(route, ['kind', 'platform', 'ownerId', 'threadId'], 'callback route');
  if (route.kind !== 'exact-thread' || route.platform !== binding.platform
      || route.ownerId !== binding.ownerId || route.threadId !== binding.threadId) {
    throw new Error('Invalid callback origin: must be the exact verified owner/thread');
  }
}

function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function keyBuffer(key, label) {
  if (!Buffer.isBuffer(key) || key.length < 32) throw new Error(`${label} must be a private 32+ byte Buffer`);
  return key;
}

function mac(assertion, key) {
  return createHmac('sha256', key).update(AUDIENCE).update('\0').update(stableJson(assertion)).digest('hex');
}

// This signing primitive is for a trusted, independently authenticated
// platform-authority adapter ONLY. It is never an end-user registration API.
export function signOriginAssertion(unsigned, authorityKey) {
  keyBuffer(authorityKey, 'Authority signing key');
  const payload = JSON.parse(stableJson(unsigned));
  delete payload.signature;
  return { ...payload, signature: mac(payload, authorityKey) };
}

function validateAssertion(assertion, purpose, trustedIssuers, signingKey, now) {
  exactObject(assertion, [
    'version', 'purpose', 'issuer', 'binding', 'nonce', 'issuedAt', 'expiresAt', 'signature',
  ], 'signed assertion');
  if (assertion.version !== 1 || assertion.purpose !== purpose) throw new Error('Invalid assertion purpose/version');
  if (!trustedIssuers.has(assertion.issuer)) throw new Error('Untrusted assertion issuer');
  assertIdentifier(assertion.issuer, 'issuer');
  validateBinding(assertion.binding);
  if (trustedIssuers.get(assertion.issuer) !== assertion.binding.platform) {
    throw new Error('Untrusted issuer for origin platform');
  }
  if (!UUID.test(assertion.nonce)) throw new Error('Invalid assertion nonce');
  if (!Number.isSafeInteger(assertion.issuedAt) || !Number.isSafeInteger(assertion.expiresAt)
      || assertion.expiresAt <= assertion.issuedAt
      || assertion.expiresAt - assertion.issuedAt > MAX_ASSERTION_LIFETIME_MS
      || assertion.issuedAt > now + MAX_CLOCK_SKEW_MS
      || assertion.expiresAt <= now) {
    throw new Error('Invalid, expired or future assertion time');
  }
  if (assertion.binding.authorizationExpiresAt <= now) throw new Error('Origin authorization expired');
  if (typeof assertion.signature !== 'string' || !SHA256.test(assertion.signature)) {
    throw new Error('Invalid assertion signature');
  }
  const { signature, ...payload } = assertion;
  const expected = Buffer.from(mac(payload, signingKey), 'hex');
  if (!timingSafeEqual(expected, Buffer.from(signature, 'hex'))) {
    throw new Error('Invalid assertion signature');
  }
}

function deriveEncryptionKey(key) {
  return Buffer.from(hkdfSync('sha256', key, Buffer.from('vera-510-private-origin'),
    Buffer.from('aes-256-gcm/private-registry/v1'), 32));
}

function ensurePrivateDirectory(directory) {
  if (!existsSync(directory)) mkdirSync(directory, { recursive: true, mode: PRIVATE_DIR_MODE });
  const stat = lstatSync(directory);
  if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error('Private registry directory is a symlink or not a directory');
  if ((stat.mode & 0o777) !== PRIVATE_DIR_MODE
      || (process.getuid && stat.uid !== process.getuid())) {
    throw new Error('Unsafe private registry directory permissions/ownership');
  }
}

function ensurePrivateFile(file) {
  let stat;
  try { stat = lstatSync(file); }
  catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('Registry path is a symbolic link or not a regular file');
  if ((stat.mode & 0o777) !== PRIVATE_FILE_MODE
      || stat.nlink !== 1
      || (process.getuid && stat.uid !== process.getuid())) {
    throw new Error('Unsafe private registry file permissions/ownership');
  }
  return true;
}

function readState(file, key) {
  if (!ensurePrivateFile(file)) return { entries: {}, spentNonces: [] };
  let envelope;
  try {
    envelope = JSON.parse(readFileSync(file, 'utf8'));
    exactObject(envelope, ['version', 'iv', 'ciphertext', 'tag'], 'encrypted registry');
    if (envelope.version !== 1 || ![envelope.iv, envelope.ciphertext, envelope.tag].every(x => typeof x === 'string')
        || !/^[a-f0-9]{24}$/.test(envelope.iv) || !/^[a-f0-9]{32}$/.test(envelope.tag)
        || !/^[a-f0-9]+$/.test(envelope.ciphertext)) throw new Error('Invalid encrypted registry encoding');
    const decipher = createDecipheriv('aes-256-gcm', key, Buffer.from(envelope.iv, 'hex'));
    decipher.setAuthTag(Buffer.from(envelope.tag, 'hex'));
    const plain = Buffer.concat([decipher.update(Buffer.from(envelope.ciphertext, 'hex')), decipher.final()]);
    const data = JSON.parse(plain.toString('utf8'));
    exactObject(data, ['entries', 'spentNonces'], 'private registry state');
    if (!data.entries || typeof data.entries !== 'object' || Array.isArray(data.entries)
        || !Array.isArray(data.spentNonces)) throw new Error('Invalid private registry state');
    return data;
  } catch {
    // Never silently reset a corrupted or unauthenticated registry: that would
    // lose spent nonces and allow re-binding previously claimed operations.
    throw new Error('Private registry integrity check failed (corrupt or invalid encrypted file)');
  }
}

function writeState(file, key, state) {
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', key, iv);
  const ciphertext = Buffer.concat([cipher.update(stableJson(state), 'utf8'), cipher.final()]);
  const envelope = JSON.stringify({ version: 1, iv: iv.toString('hex'),
    ciphertext: ciphertext.toString('hex'), tag: cipher.getAuthTag().toString('hex') }) + '\n';
  const temp = `${file}.${randomUUID()}.tmp`;
  let fd;
  try {
    fd = openSync(temp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, PRIVATE_FILE_MODE);
    writeSync(fd, envelope);
    fsyncSync(fd);
    closeSync(fd);
    fd = undefined;
    renameSync(temp, file);
    // fsync the containing directory so rename durability is not dependent
    // solely on a successful process exit.
    const directoryFd = openSync(path.dirname(file), constants.O_RDONLY);
    try { fsyncSync(directoryFd); } finally { closeSync(directoryFd); }
  } finally {
    if (fd !== undefined) closeSync(fd);
    if (existsSync(temp)) unlinkSync(temp);
  }
}

// The registry is a single-writer private service: no stale-lock stealing.
// Failure to acquire a lock or to read authenticated state is fail-closed.
export function createOriginRegistry({ filePath, signingKey, encryptionKey, trustedIssuers, now = Date.now }) {
  if (typeof filePath !== 'string' || !path.isAbsolute(filePath)) throw new Error('Registry filePath must be absolute');
  keyBuffer(signingKey, 'Authority signing key');
  keyBuffer(encryptionKey, 'Registry encryption key');
  if (!trustedIssuers || typeof trustedIssuers !== 'object' || Array.isArray(trustedIssuers)
      || Object.keys(trustedIssuers).length === 0
      || Object.entries(trustedIssuers).some(([issuer, platform]) => !IDENTIFIER.test(issuer) || !PLATFORMS.has(platform))) {
    throw new Error('Trusted issuers must map each issuer to one authorized platform');
  }
  const issuers = new Map(Object.entries(trustedIssuers));
  const atRestKey = deriveEncryptionKey(encryptionKey);

  function withState(operation) {
    const directory = path.dirname(filePath);
    ensurePrivateDirectory(directory);
    const lockPath = `${filePath}.lock`;
    let lockFd;
    try {
      lockFd = openSync(lockPath, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, PRIVATE_FILE_MODE);
    } catch {
      throw new Error('Private origin registry locked; no unsafe lock stealing');
    }
    try {
      // Check before and after acquiring the lock to avoid following a
      // maliciously replaced path even when another instance exists.
      ensurePrivateFile(filePath);
      const state = readState(filePath, atRestKey);
      const result = operation(state);
      writeState(filePath, atRestKey, state);
      return result;
    } finally {
      closeSync(lockFd);
      unlinkSync(lockPath);
    }
  }

  function validated(assertion, purpose) {
    validateAssertion(assertion, purpose, issuers, signingKey, now());
    // Copy canonical JSON to prevent caller mutations during persistence.
    return JSON.parse(stableJson(assertion));
  }

  function consumeNonce(state, assertion) {
    const spent = `${assertion.issuer}:${assertion.nonce}`;
    if (state.spentNonces.includes(spent)) throw new Error('Replay of origin assertion nonce');
    state.spentNonces.push(spent);
  }

  function registerOrigin(attestation) {
    const signed = validated(attestation, 'register');
    return withState(state => {
      const binding = signed.binding;
      consumeNonce(state, signed);
      if (Object.hasOwn(state.entries, binding.correlationId)) throw new Error('Conflicting origin correlation ID');
      const operationKey = stableJson([
        binding.repository, binding.issueNumber, binding.jobId, binding.caseId, binding.operationId,
      ]);
      if (Object.values(state.entries).some(entry => entry.operationKey === operationKey)) {
        throw new Error('Conflicting origin operation identity');
      }
      const bindingId = randomUUID();
      state.entries[binding.correlationId] = {
        binding, issuer: signed.issuer, operationKey, bindingId, registeredAt: now(),
      };
      // Return only public, opaque correlation metadata, never the owner/thread.
      return { bindingId, correlationId: binding.correlationId };
    });
  }

  function resolveOrigin(attestation) {
    const signed = validated(attestation, 'resolve');
    return withState(state => {
      consumeNonce(state, signed);
      const entry = Object.hasOwn(state.entries, signed.binding.correlationId)
        ? state.entries[signed.binding.correlationId] : null;
      if (!entry) throw new Error('Unknown origin correlation ID');
      if (entry.issuer !== signed.issuer || stableJson(entry.binding) !== stableJson(signed.binding)) {
        throw new Error('Origin mismatch: refusing foreign, redirected or stale binding');
      }
      if (entry.binding.authorizationExpiresAt <= now()) throw new Error('Origin authorization expired');
      return JSON.parse(stableJson(entry.binding));
    });
  }

  return Object.freeze({ registerOrigin, resolveOrigin });
}
