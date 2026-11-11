// #510 phase 3: code-only, manual-first delivery state machine.
// There is deliberately NO production sender, network client, user-role
// injection, paid turn, native Test Bench callback, or live wake hook here.
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
import { verifyTerminalEvent } from './test-bench-terminal-outbox.mjs';

const DOMAIN = 'vera.test-bench.independent-thread-observation/v1';
const TARGET_DOMAIN = 'vera.test-bench.private-delivery-target/v1';
const PLATFORMS = ['codex', 'zodex', 'chatgpt'];
const OBSERVATIONS = {
  ack_observed: 'platform-delivery-ack',
  auto_woke: 'unloaded-thread-activation',
  reviewed: 'thread-content-review',
  resumed: 'thread-agent-resumption',
};
const STATES = new Set([
  'persisted', 'queued', 'in_flight', 'delivered', 'ack_observed',
  'auto_woke', 'reviewed', 'resumed', 'unknown', 'failed', 'expired',
]);
const SHA = /^[a-f0-9]{64}$/;
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9_.:@-]{0,255}$/;
const MAX_ATTEMPTS = 3;
const MAX_DELIVERY_MS = 24 * 60 * 60 * 1000;
const OBSERVATION_LIFETIME_MS = 5 * 60 * 1000;
const CLOCK_SKEW_MS = 30_000;
const RETRY_MS = [30_000, 60_000, 120_000];

// Concrete supported-platform adapter slots. They expose capability probes
// but never accept a transport, credential or arbitrary callback. #511 must
// implement separately reviewed platform integrations, not toggle these on.
export function createSupportedPlatformSenderAdapters() {
  return Object.freeze(Object.fromEntries(PLATFORMS.map(platform => [
    platform,
    Object.freeze({
      platform,
      capability: Object.freeze({ supportedPlatform: true, productionSendEnabled: false }),
      send() { throw new Error(platform + ' production exact-thread sender hard-disabled'); },
    }),
  ])));
}

function exact(value, keys, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)
      || Object.keys(value).length !== keys.length
      || keys.some(name => !Object.hasOwn(value, name))) {
    throw new Error('Invalid ' + label + ' fields');
  }
}
function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value !== null && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
  }
  return JSON.stringify(value);
}
function clone(value) { return JSON.parse(canonical(value)); }
function secret(value, label) {
  if (!Buffer.isBuffer(value) || value.length < 32) throw new Error(label + ' must be a private 32+ byte Buffer');
  return value;
}
function mac(domain, payload, key) {
  return createHmac('sha256', key).update(domain).update('\0').update(canonical(payload)).digest('hex');
}
function equalHex(a, b) {
  return typeof a === 'string' && SHA.test(a)
    && timingSafeEqual(Buffer.from(a, 'hex'), Buffer.from(b, 'hex'));
}
function validTime(value) { return Number.isSafeInteger(value) && value > 0; }
function assertId(value, label) {
  if (typeof value !== 'string' || !IDENTIFIER.test(value)) throw new Error('Invalid ' + label);
}
function assertEventId(value) {
  if (typeof value !== 'string' || !SHA.test(value)) throw new Error('Invalid event ID');
}
function targetMac(route, key) { return mac(TARGET_DOMAIN, route, key); }
function targetRoute(platform, ownerId, threadId) {
  return { kind: 'exact-thread', platform, ownerId, threadId };
}

// This helper is solely a fixture primitive for independently authenticated
// platform observers. It is NOT a service that signs chat text or send results.
export function signDeliveryObservation(unsigned, observerKey) {
  secret(observerKey, 'Observer signing key');
  const copy = clone(unsigned);
  delete copy.signature;
  return { ...copy, signature: mac(DOMAIN, copy, observerKey) };
}

function verifyObservation(observation, observers, at) {
  exact(observation, [
    'version', 'issuer', 'kind', 'deliveryId', 'eventId', 'correlationId', 'bindingId',
    'platform', 'ownerId', 'threadId', 'messageId', 'evidenceKind', 'evidenceSha256',
    'nonce', 'issuedAt', 'expiresAt', 'signature',
  ], 'signed platform observation');
  if (observation.version !== 1 || !Object.hasOwn(OBSERVATIONS, observation.kind)) {
    throw new Error('Invalid independent observation kind/version');
  }
  assertId(observation.issuer, 'observation issuer');
  const observer = observers.get(observation.issuer);
  if (!observer || observer.platform !== observation.platform) throw new Error('Untrusted independent observer/platform');
  for (const name of ['ownerId', 'threadId', 'messageId']) assertId(observation[name], name);
  if (!PLATFORMS.includes(observation.platform) || !UUID.test(observation.deliveryId)
      || !UUID.test(observation.correlationId) || !UUID.test(observation.bindingId)
      || !UUID.test(observation.nonce)) throw new Error('Invalid observation correlation/destination');
  assertEventId(observation.eventId);
  if (observation.evidenceKind !== OBSERVATIONS[observation.kind]
      || typeof observation.evidenceSha256 !== 'string' || !SHA.test(observation.evidenceSha256)) {
    throw new Error('Invalid independently observed evidence kind/digest');
  }
  if (!validTime(observation.issuedAt) || !validTime(observation.expiresAt)
      || observation.expiresAt <= observation.issuedAt
      || observation.expiresAt - observation.issuedAt > OBSERVATION_LIFETIME_MS
      || observation.issuedAt > at + CLOCK_SKEW_MS || observation.expiresAt <= at) {
    throw new Error('Expired/future independent observation');
  }
  const { signature, ...payload } = observation;
  if (!equalHex(signature, mac(DOMAIN, payload, observer.key))) {
    throw new Error('Invalid independent observation signature');
  }
  return clone(observation);
}

function ensurePrivateDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true, mode: 0o700 });
  const s = lstatSync(dir);
  if (!s.isDirectory() || s.isSymbolicLink() || (s.mode & 0o777) !== 0o700
      || (process.getuid && s.uid !== process.getuid())) throw new Error('Unsafe private delivery directory');
}
function privateFile(file) {
  let s;
  try { s = lstatSync(file); } catch (e) { if (e.code === 'ENOENT') return false; throw e; }
  if (!s.isFile() || s.isSymbolicLink() || (s.mode & 0o777) !== 0o600 || s.nlink !== 1
      || (process.getuid && s.uid !== process.getuid())) throw new Error('Unsafe private delivery file');
  return true;
}
function emptyState() { return { version: 1, deliveries: {}, spentNonces: [] }; }
function validateState(state) {
  exact(state, ['version', 'deliveries', 'spentNonces'], 'delivery store');
  if (state.version !== 1 || !state.deliveries || typeof state.deliveries !== 'object'
      || Array.isArray(state.deliveries) || !Array.isArray(state.spentNonces)
      || new Set(state.spentNonces).size !== state.spentNonces.length) {
    throw new Error('Invalid delivery store state');
  }
  for (const [eventId, record] of Object.entries(state.deliveries)) {
    assertEventId(eventId);
    exact(record, [
      'eventId', 'deliveryId', 'bindingId', 'correlationId', 'platform', 'targetMac',
      'status', 'expiresAt', 'attempts', 'retryAt', 'messageId', 'claimId',
      'lastFault', 'history',
    ], 'delivery record');
    if (record.eventId !== eventId || !UUID.test(record.deliveryId)
        || !UUID.test(record.bindingId) || !UUID.test(record.correlationId)
        || !PLATFORMS.includes(record.platform) || !SHA.test(record.targetMac)
        || !STATES.has(record.status) || !validTime(record.expiresAt)
        || !Number.isSafeInteger(record.attempts) || record.attempts < 0
        || record.attempts > MAX_ATTEMPTS || !Number.isSafeInteger(record.retryAt)
        || record.retryAt < 0 || (record.messageId !== null && !IDENTIFIER.test(record.messageId))
        || (record.claimId !== null && !UUID.test(record.claimId))
        || (record.lastFault !== null && !IDENTIFIER.test(record.lastFault))
        || !Array.isArray(record.history) || record.history.length < 2
        || record.history[0].state !== 'persisted' || record.history[1].state !== 'queued'
        || record.history.at(-1).state !== record.status
        || record.history.some(h => !h || !STATES.has(h.state) || !validTime(h.at))
        || (record.status === 'in_flight') !== (record.claimId !== null)) {
      throw new Error('Invalid delivery state/history integrity');
    }
  }
  for (const nonce of state.spentNonces) {
    if (typeof nonce !== 'string' || !/^[A-Za-z0-9_.:@-]+:[a-f0-9-]{36}$/i.test(nonce)) {
      throw new Error('Invalid persisted observer nonce');
    }
  }
}
function read(file, encryptionKey) {
  if (!privateFile(file)) return emptyState();
  try {
    const envelope = JSON.parse(readFileSync(file, 'utf8'));
    exact(envelope, ['version', 'iv', 'ciphertext', 'tag'], 'encrypted delivery store');
    if (envelope.version !== 1 || !/^[a-f0-9]{24}$/.test(envelope.iv)
        || !/^[a-f0-9]{32}$/.test(envelope.tag)
        || !/^(?:[a-f0-9]{2})+$/.test(envelope.ciphertext)) {
      throw new Error('Invalid encrypted delivery store');
    }
    const decipher = createDecipheriv('aes-256-gcm', encryptionKey, Buffer.from(envelope.iv, 'hex'));
    decipher.setAuthTag(Buffer.from(envelope.tag, 'hex'));
    const state = JSON.parse(Buffer.concat([
      decipher.update(Buffer.from(envelope.ciphertext, 'hex')), decipher.final(),
    ]).toString('utf8'));
    validateState(state);
    return state;
  } catch {
    throw new Error('Private delivery integrity failure; no reset or replay');
  }
}
function save(file, encryptionKey, state) {
  validateState(state);
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', encryptionKey, iv);
  const encrypted = Buffer.concat([cipher.update(canonical(state), 'utf8'), cipher.final()]);
  const document = JSON.stringify({
    version: 1, iv: iv.toString('hex'), ciphertext: encrypted.toString('hex'),
    tag: cipher.getAuthTag().toString('hex'),
  }) + '\n';
  const temp = file + '.' + randomUUID() + '.tmp';
  let fd;
  try {
    fd = openSync(temp, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    writeSync(fd, document); fsyncSync(fd); closeSync(fd); fd = undefined;
    renameSync(temp, file);
    const dir = openSync(path.dirname(file), constants.O_RDONLY);
    try { fsyncSync(dir); } finally { closeSync(dir); }
  } finally {
    if (fd !== undefined) closeSync(fd);
    if (existsSync(temp)) unlinkSync(temp);
  }
}

function verifyMatch(event, binding, record, targetKey) {
  if (event.repository !== binding.repository || event.issueNumber !== binding.issueNumber
      || event.pullNumber !== binding.pullNumber || event.jobId !== binding.jobId
      || event.caseId !== binding.caseId || event.operationId !== binding.operationId
      || event.sourceSha256 !== binding.sourceSha256 || event.actorSha256 !== binding.actorSha256
      || event.correlationId !== binding.correlationId
      || (record && (record.bindingId !== event.bindingId
        || record.platform !== binding.platform
        || !equalHex(record.targetMac, targetMac(binding.callbackRoute, targetKey))))) {
    throw new Error('Origin/event mismatch: stale source, wrong recipient or operation');
  }
  if (binding.callbackRoute.kind !== 'exact-thread'
      || canonical(binding.callbackRoute) !== canonical(targetRoute(binding.platform, binding.ownerId, binding.threadId))) {
    throw new Error('Redirected or untrusted thread callback route');
  }
}

function publicRecord(record) {
  if (!record) return null;
  const { eventId, deliveryId, status, attempts, retryAt, expiresAt, lastFault, history } = record;
  return clone({ eventId, deliveryId, status, attempts, retryAt, expiresAt, lastFault, history });
}
function transition(record, status, time, fault = null) {
  if (!STATES.has(status)) throw new Error('Unknown delivery state');
  record.status = status;
  record.claimId = null;
  record.lastFault = fault;
  record.history.push({ state: status, at: time });
}

function validateSimulationPlans(plans) {
  if (plans === null) return null;
  if (!plans || typeof plans !== 'object' || Array.isArray(plans)
      || Object.keys(plans).some(p => !PLATFORMS.includes(p))) {
    throw new Error('Invalid simulation-only sender plans');
  }
  for (const outcomes of Object.values(plans)) {
    if (!Array.isArray(outcomes) || outcomes.length > MAX_ATTEMPTS) throw new Error('Invalid bounded simulation attempts');
    for (const outcome of outcomes) {
      if (!outcome || typeof outcome !== 'object' || Array.isArray(outcome)
          || !['delivered', 'offline', 'busy', 'ambiguous', 'rejected', 'crash'].includes(outcome.kind)
          || (outcome.kind === 'delivered'
            ? (Object.keys(outcome).sort().join(',') !== 'kind,messageId,recipient'
              || !IDENTIFIER.test(outcome.messageId)
              || !outcome.recipient || typeof outcome.recipient !== 'object')
            : Object.keys(outcome).join(',') !== 'kind')) {
        throw new Error('Invalid simulated sender outcome');
      }
    }
  }
  return clone(plans);
}

export function createExactThreadDelivery({
  filePath, outbox, registry, eventKey, encryptionKey, observerKeys,
  now = Date.now, simulationPlans = null,
}) {
  if (typeof filePath !== 'string' || !path.isAbsolute(filePath)) throw new Error('Delivery path must be absolute');
  if (!outbox || typeof outbox.inspect !== 'function'
      || !registry || typeof registry.resolveRegisteredOrigin !== 'function') {
    throw new Error('Trusted event and origin stores required');
  }
  secret(eventKey, 'Event signing key'); secret(encryptionKey, 'Delivery encryption key');
  if (!observerKeys || typeof observerKeys !== 'object' || Array.isArray(observerKeys)
      || !Object.keys(observerKeys).length) throw new Error('Independent observation authorities required');
  const observers = new Map(Object.entries(observerKeys).map(([issuer, cfg]) => {
    assertId(issuer, 'independent observer');
    exact(cfg, ['platform', 'key'], 'independent observer configuration');
    if (!PLATFORMS.includes(cfg.platform)) throw new Error('Unsupported observer platform');
    return [issuer, { platform: cfg.platform, key: secret(cfg.key, 'Observer key') }];
  }));
  // Static response plans only: no arbitrary sender callback or network
  // transport can be supplied. Production stays disabled in every build.
  const simulations = validateSimulationPlans(simulationPlans);
  const productionSenders = createSupportedPlatformSenderAdapters();
  const atRestKey = Buffer.from(hkdfSync('sha256', encryptionKey,
    Buffer.from('vera-510-delivery'), Buffer.from('aes-256-gcm/lifecycle/v1'), 32));

  function withState(write, operation) {
    ensurePrivateDir(path.dirname(filePath));
    let fd;
    try {
      fd = openSync(filePath + '.lock', constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    } catch { throw new Error('Private delivery locked; no lock stealing'); }
    try {
      const state = read(filePath, atRestKey);
      const result = operation(state);
      if (write) save(filePath, atRestKey, state);
      return result;
    } finally { closeSync(fd); unlinkSync(filePath + '.lock'); }
  }
  function trustedEvent(eventId) {
    assertEventId(eventId);
    const found = outbox.inspect(eventId);
    if (!found || found.audit?.status !== 'persisted') throw new Error('Unknown, unpersisted terminal event');
    const event = verifyTerminalEvent(found.event, eventKey);
    if (event.eventId !== eventId) throw new Error('Event identity mismatch');
    return event;
  }
  function resolved(event, assertion, record = null) {
    // Resolution is independently signed, fresh, and spent in the phase-1
    // private registry. Event correlation alone is never enough to send.
    const { binding, bindingId } = registry.resolveRegisteredOrigin(assertion);
    if (bindingId !== event.bindingId) throw new Error('Origin binding ID mismatch');
    verifyMatch(event, binding, record, encryptionKey);
    return binding;
  }
  function capabilities() {
    return Object.fromEntries(PLATFORMS.map(platform => [platform, {
      productionSendEnabled: productionSenders[platform].capability.productionSendEnabled,
      mode: simulations === null ? 'disabled' : 'simulation-only',
      independentlyObservedLiveWake: false,
    }]));
  }
  function enqueue({ eventId, resolveAssertion }) {
    const event = trustedEvent(eventId);
    const binding = resolved(event, resolveAssertion);
    return withState(true, state => {
      if (Object.hasOwn(state.deliveries, eventId)) {
        verifyMatch(event, binding, state.deliveries[eventId], encryptionKey);
        return publicRecord(state.deliveries[eventId]);
      }
      const at = now();
      const expiry = Math.min(at + MAX_DELIVERY_MS, binding.authorizationExpiresAt);
      if (expiry <= at) throw new Error('Expired destination authorization');
      const record = {
        eventId, deliveryId: randomUUID(), bindingId: event.bindingId,
        correlationId: event.correlationId, platform: binding.platform,
        targetMac: targetMac(binding.callbackRoute, encryptionKey),
        status: 'queued', expiresAt: expiry, attempts: 0, retryAt: at,
        messageId: null, claimId: null, lastFault: null,
        history: [{ state: 'persisted', at }, { state: 'queued', at }],
      };
      state.deliveries[eventId] = record;
      return publicRecord(record);
    });
  }
  function dispatch({ eventId, resolveAssertion }) {
    // This is the independent proof that production sending is hard-disabled:
    // there is no bypass via an environment flag, callback, or credential.
    if (simulations === null) throw new Error('Production exact-thread sender hard-disabled');
    const event = trustedEvent(eventId);
    if (event.provenance !== 'simulation') throw new Error('Real/historical sends hard-disabled');
    const binding = resolved(event, resolveAssertion);
    const claim = withState(true, state => {
      const record = state.deliveries[eventId];
      if (!record) throw new Error('Event has not been queued');
      verifyMatch(event, binding, record, encryptionKey);
      if (record.status === 'in_flight') {
        transition(record, 'unknown', now(), 'claim_without_definitive_receipt');
        return { accepted: false, snapshot: publicRecord(record) };
      }
      if (now() >= record.expiresAt) {
        if (record.status !== 'resumed' && record.status !== 'unknown'
            && record.status !== 'failed' && record.status !== 'expired') {
          transition(record, record.status === 'delivered' ? 'unknown' : 'expired', now(), 'delivery_expired');
        }
        return { accepted: false, snapshot: publicRecord(record) };
      }
      if (record.status !== 'queued') throw new Error('Delivery already sent, observed or terminal');
      if (record.attempts >= MAX_ATTEMPTS || now() < record.retryAt) {
        throw new Error('Retry limit or backoff not elapsed');
      }
      record.attempts += 1;
      record.claimId = randomUUID();
      record.status = 'in_flight';
      record.history.push({ state: 'in_flight', at: now() });
      return { accepted: true, claimId: record.claimId, attempt: record.attempts };
    });
    if (!claim.accepted) return claim.snapshot;

    // Static, deterministic simulated response; no platform calls. Commit the
    // in-flight claim BEFORE handling it. A crash/lost response stays UNKNOWN,
    // never replayed as a second submission.
    const response = simulations[binding.platform]?.[claim.attempt - 1] ?? { kind: 'ambiguous' };
    if (response.kind === 'crash') throw new Error('Simulated crash after durable send claim');
    return withState(true, state => {
      const record = state.deliveries[eventId];
      if (!record || record.status !== 'in_flight' || record.claimId !== claim.claimId) {
        throw new Error('Lost or conflicting delivery claim');
      }
      if (now() >= record.expiresAt) {
        transition(record, 'unknown', now(), 'expired_during_send');
      } else if (response.kind === 'delivered'
          && canonical(response.recipient) === canonical(binding.callbackRoute)) {
        record.messageId = response.messageId;
        transition(record, 'delivered', now());
      } else if (response.kind === 'offline' || response.kind === 'busy') {
        if (record.attempts >= MAX_ATTEMPTS) {
          transition(record, 'failed', now(), 'safe_retry_exhausted');
        } else {
          record.retryAt = now() + RETRY_MS[record.attempts - 1];
          transition(record, 'queued', now(), response.kind + '_not_enqueued');
        }
      } else if (response.kind === 'rejected') {
        transition(record, 'failed', now(), 'definitively_rejected');
      } else {
        transition(record, 'unknown', now(), 'ambiguous_or_wrong_recipient');
      }
      return publicRecord(record);
    });
  }
  function observe(signedObservation) {
    const observation = verifyObservation(signedObservation, observers, now());
    const event = trustedEvent(observation.eventId);
    return withState(true, state => {
      const record = state.deliveries[observation.eventId];
      if (!record) throw new Error('Unknown delivery observation');
      if (now() >= record.expiresAt) throw new Error('Expired delivery observation window');
      if (record.eventId !== event.eventId || record.deliveryId !== observation.deliveryId
          || record.bindingId !== observation.bindingId
          || record.correlationId !== observation.correlationId
          || record.platform !== observation.platform
          || !equalHex(record.targetMac, targetMac(targetRoute(
            observation.platform, observation.ownerId, observation.threadId), encryptionKey))
          || record.messageId !== observation.messageId) {
        throw new Error('Wrong recipient, stale source, message or ACK correlation');
      }
      const transitions = {
        delivered: 'ack_observed', ack_observed: 'auto_woke',
        auto_woke: 'reviewed', reviewed: 'resumed',
      };
      if (transitions[record.status] !== observation.kind) {
        throw new Error('Unproven or out-of-order platform observation');
      }
      const nonce = observation.issuer + ':' + observation.nonce;
      if (state.spentNonces.includes(nonce)) throw new Error('Replayed platform observation');
      state.spentNonces.push(nonce);
      transition(record, observation.kind, now());
      return publicRecord(record);
    });
  }
  function inspect(eventId) {
    trustedEvent(eventId);
    return withState(false, state => publicRecord(state.deliveries[eventId] ?? null));
  }
  function sweep(eventId) {
    trustedEvent(eventId);
    return withState(true, state => {
      const record = state.deliveries[eventId];
      if (!record) return null;
      if (record.status === 'in_flight') {
        transition(record, 'unknown', now(), 'claim_without_definitive_receipt');
      } else if (now() >= record.expiresAt && !['resumed', 'failed', 'expired', 'unknown'].includes(record.status)) {
        transition(record, record.status === 'queued' ? 'expired' : 'unknown', now(), 'delivery_expired_without_proof');
      }
      return publicRecord(record);
    });
  }
  function manualFallback(eventId) {
    const event = trustedEvent(eventId);
    const delivery = inspect(eventId);
    return Object.freeze({
      kind: 'manual-owner-handoff', source: '#398',
      instructions: 'Owner manually opens the exact originating thread and reviews the pinned report; never interpret this as a wake.',
      eventId, correlationId: event.correlationId, outcome: event.outcome,
      report: clone(event.report),
      deliveryStatus: delivery?.status ?? 'persisted',
      scheduledOwnerCheck: { source: '#421', kind: 'optional-scheduled-owner-check', countsAsWakeEvidence: false },
      independentLiveWakeProven: false, strict312Verdict: 'UNPROVED',
    });
  }
  return Object.freeze({ capabilities, enqueue, dispatch, observe, inspect, sweep, manualFallback });
}
